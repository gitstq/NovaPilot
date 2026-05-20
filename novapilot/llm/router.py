"""Intelligent LLM router for NovaPilot.

Routes requests to the optimal LLM backend based on task type,
model capabilities, and availability. Supports load balancing
and automatic failover between backends.
"""

import re
import time
from novapilot.llm.base import LLMBackend, LLMError
from novapilot.llm.openai_backend import OpenAIBackend
from novapilot.llm.anthropic_backend import AnthropicBackend
from novapilot.llm.ollama_backend import OllamaBackend


# Task type classification patterns
TASK_PATTERNS = {
    "code_generation": {
        "patterns": [
            r'\b(write|create|implement|build|generate|code|program)\b',
            r'\b(function|class|method|module|script|algorithm)\b',
            r'\b(python|javascript|typescript|java|c\+\+|rust|go)\b',
            r'\b(debug|fix|refactor|optimize)\b.*\b(code|function|class)\b',
            r'^```[\w]*\s*$',
        ],
        "preferred": ["openai", "anthropic"],
        "min_capability": "strong",
    },
    "long_document": {
        "patterns": [
            r'\b(summarize|analyze|review|read)\b.*\b(document|file|article|paper|report|text)\b',
            r'\b(long|large|big)\b.*\b(text|document|content|context)\b',
            r'\b(extract|find|search)\b.*\b(from|in)\b.*\b(document|text|file)\b',
        ],
        "preferred": ["anthropic"],
        "min_capability": "large_context",
    },
    "simple_qa": {
        "patterns": [
            r'^(what|who|when|where|why|how|is|are|can|do|does|will|would)\b',
            r'\b(define|explain|describe|tell me)\b',
            r'^(hi|hello|hey|greetings)',
            r'^\?$',
        ],
        "preferred": ["ollama", "openai"],
        "min_capability": "lightweight",
    },
    "creative_writing": {
        "patterns": [
            r'\b(write|compose|draft|create)\b.*\b(story|poem|essay|article|blog|email|letter|novel|narrative)\b',
            r'\b(creative|fiction|novel|narrative)\b',
            r'\b(rewrite|paraphrase|rephrase)\b',
            r'\bshort story\b',
        ],
        "preferred": ["anthropic", "openai"],
        "min_capability": "strong",
    },
    "data_analysis": {
        "patterns": [
            r'\b(analyze|calculate|compute|process)\b.*\b(data|numbers|statistics|metrics)\b',
            r'\b(csv|json|excel|spreadsheet|database|sql)\b',
            r'\b(chart|graph|plot|visuali[zs]e)\b',
        ],
        "preferred": ["openai", "anthropic"],
        "min_capability": "strong",
    },
    "translation": {
        "patterns": [
            r'\b(translate|translation|convert)\b.*\b(to|into|from)\b',
            r'\b(english|chinese|japanese|korean|french|german|spanish)\b',
        ],
        "preferred": ["openai", "anthropic"],
        "min_capability": "lightweight",
    },
}

# Backend capability definitions
BACKEND_CAPABILITIES = {
    "openai": {
        "strength": "strong",
        "context_window": 128000,
        "supports_streaming": True,
        "supports_functions": True,
        "cost_level": "paid",
    },
    "anthropic": {
        "strength": "strong",
        "context_window": 200000,
        "supports_streaming": True,
        "supports_functions": False,
        "cost_level": "paid",
    },
    "ollama": {
        "strength": "varies",
        "context_window": 8192,
        "supports_streaming": True,
        "supports_functions": False,
        "cost_level": "free",
    },
}

# Capability level requirements
CAPABILITY_LEVELS = {
    "lightweight": ["ollama", "openai", "anthropic"],
    "strong": ["openai", "anthropic"],
    "large_context": ["anthropic", "openai"],
}


class LLMRouter:
    """Intelligent LLM backend router.

    Analyzes incoming requests to determine the optimal backend,
    handles load balancing across multiple backends, and provides
    automatic failover when a backend is unavailable.
    """

    def __init__(self, config_manager):
        """Initialize LLMRouter.

        Args:
            config_manager: ConfigManager instance for backend configuration.
        """
        self.config_manager = config_manager
        self._backends = {}
        self._backend_health = {}
        self._request_counts = {}
        self._init_backends()

    def _init_backends(self):
        """Initialize all configured and enabled backends.

        Creates backend instances from configuration and performs
        initial health checks.
        """
        backends_config = self.config_manager.list_backends()

        for backend_info in backends_config:
            name = backend_info["name"]
            if not backend_info.get("enabled", False):
                continue

            config = self.config_manager.get_backend(name)
            if config is None:
                continue

            try:
                backend = self._create_backend(name, config)
                self._backends[name] = backend
                self._request_counts[name] = 0
                # Initial health check (non-blocking)
                self._backend_health[name] = True
            except Exception:
                self._backend_health[name] = False

    def _create_backend(self, name, config):
        """Create a backend instance based on its type.

        Args:
            name: Backend name.
            config: Backend configuration dict.

        Returns:
            LLMBackend instance.

        Raises:
            ValueError: If backend type is unknown.
        """
        backend_type = config.get("type", "")

        if backend_type == "openai":
            return OpenAIBackend(name=name, config=config)
        elif backend_type == "anthropic":
            return AnthropicBackend(name=name, config=config)
        elif backend_type == "ollama":
            return OllamaBackend(name=name, config=config)
        else:
            raise ValueError(f"Unknown backend type: {backend_type}")

    def classify_task(self, prompt):
        """Classify the type of task based on the prompt content.

        Analyzes the prompt against predefined patterns to determine
        the task type (code generation, Q&A, document analysis, etc.).

        Args:
            prompt: User prompt text.

        Returns:
            String task type identifier.
        """
        prompt_lower = prompt.lower().strip()

        best_match = "simple_qa"
        best_score = 0

        # Priority order: simple patterns should be checked with a bonus
        # when they match at the start of the prompt
        for task_type, task_info in TASK_PATTERNS.items():
            score = 0
            for pattern in task_info["patterns"]:
                if re.search(pattern, prompt_lower, re.IGNORECASE):
                    score += 1
                    # Bonus for patterns that anchor to start of prompt
                    if pattern.startswith("^"):
                        score += 2
            if score > best_score:
                best_score = score
                best_match = task_type

        return best_match

    def select_backend(self, prompt=None, task_type=None, preferred=None):
        """Select the optimal backend for a given request.

        Selection is based on:
        1. Explicit preference if provided
        2. Task classification and preferred backends
        3. Backend health and availability
        4. Load balancing (least requests)

        Args:
            prompt: User prompt for task classification.
            task_type: Explicit task type override.
            preferred: Explicit backend name override.

        Returns:
            LLMBackend instance.

        Raises:
            LLMError: If no suitable backend is available.
        """
        # Explicit preference
        if preferred and preferred in self._backends:
            if self._backend_health.get(preferred, False):
                return self._backends[preferred]

        # Classify task if prompt provided
        if task_type is None and prompt:
            task_type = self.classify_task(prompt)

        # Get preferred backends for this task type
        preferred_backends = []
        if task_type and task_type in TASK_PATTERNS:
            preferred_backends = TASK_PATTERNS[task_type]["preferred"]

        # Get minimum capability requirement
        min_capability = "lightweight"
        if task_type and task_type in TASK_PATTERNS:
            min_capability = TASK_PATTERNS[task_type]["min_capability"]

        # Filter available backends by capability
        capable_backends = CAPABILITY_LEVELS.get(min_capability, [])

        # Score each available backend
        candidates = []
        for name, backend in self._backends.items():
            if not self._backend_health.get(name, False):
                continue

            score = 0

            # Preference score
            if name in preferred_backends:
                score += 100 - preferred_backends.index(name) * 10

            # Capability match
            if name in capable_backends:
                score += 50

            # Load balancing (prefer less loaded backends)
            request_count = self._request_counts.get(name, 0)
            score += max(0, 100 - request_count)

            # Free tier preference for simple tasks
            if min_capability == "lightweight":
                cost = BACKEND_CAPABILITIES.get(name, {}).get("cost_level", "")
                if cost == "free":
                    score += 30

            candidates.append((name, backend, score))

        if not candidates:
            # Fallback: try any available backend
            for name, backend in self._backends.items():
                return backend
            raise LLMError(
                "No LLM backends available. Please configure at least one backend.",
                backend_name="router",
            )

        # Sort by score (highest first) and return the best
        candidates.sort(key=lambda x: x[2], reverse=True)
        selected_name, selected_backend, _ = candidates[0]
        self._request_counts[selected_name] = self._request_counts.get(
            selected_name, 0
        ) + 1

        return selected_backend

    def complete(self, prompt, system_prompt=None, temperature=None,
                 max_tokens=None, backend_name=None, **kwargs):
        """Route a completion request to the optimal backend.

        Args:
            prompt: User prompt text.
            system_prompt: Optional system prompt.
            temperature: Sampling temperature.
            max_tokens: Maximum response tokens.
            backend_name: Explicit backend name (bypasses routing).
            **kwargs: Additional parameters.

        Returns:
            Dict with 'content', 'usage', 'model', and 'backend' keys.

        Raises:
            LLMError: If all backends fail.
        """
        backend = self.select_backend(
            prompt=prompt, preferred=backend_name
        )

        try:
            result = backend.complete(
                prompt=prompt,
                system_prompt=system_prompt,
                temperature=temperature,
                max_tokens=max_tokens,
                **kwargs,
            )
            result["backend"] = backend.name
            return result
        except LLMError:
            # Failover: try other backends
            for name, other_backend in self._backends.items():
                if other_backend is backend:
                    continue
                if not self._backend_health.get(name, False):
                    continue
                try:
                    result = other_backend.complete(
                        prompt=prompt,
                        system_prompt=system_prompt,
                        temperature=temperature,
                        max_tokens=max_tokens,
                        **kwargs,
                    )
                    result["backend"] = other_backend.name
                    return result
                except LLMError:
                    continue

            raise LLMError(
                "All backends failed. Please check your configuration.",
                backend_name="router",
            )

    def stream(self, prompt, system_prompt=None, temperature=None,
               max_tokens=None, backend_name=None, **kwargs):
        """Route a streaming request to the optimal backend.

        Args:
            prompt: User prompt text.
            system_prompt: Optional system prompt.
            temperature: Sampling temperature.
            max_tokens: Maximum response tokens.
            backend_name: Explicit backend name (bypasses routing).
            **kwargs: Additional parameters.

        Yields:
            String chunks of the response.

        Raises:
            LLMError: If all backends fail.
        """
        backend = self.select_backend(
            prompt=prompt, preferred=backend_name
        )

        try:
            for chunk in backend.stream(
                prompt=prompt,
                system_prompt=system_prompt,
                temperature=temperature,
                max_tokens=max_tokens,
                **kwargs,
            ):
                yield chunk
        except LLMError:
            # Failover
            for name, other_backend in self._backends.items():
                if other_backend is backend:
                    continue
                if not self._backend_health.get(name, False):
                    continue
                try:
                    for chunk in other_backend.stream(
                        prompt=prompt,
                        system_prompt=system_prompt,
                        temperature=temperature,
                        max_tokens=max_tokens,
                        **kwargs,
                    ):
                        yield chunk
                    return
                except LLMError:
                    continue

            raise LLMError(
                "All backends failed. Please check your configuration.",
                backend_name="router",
            )

    def get_backend(self, name):
        """Get a specific backend by name.

        Args:
            name: Backend name.

        Returns:
            LLMBackend instance, or None if not found.
        """
        return self._backends.get(name)

    def list_backends(self):
        """List all initialized backends with their status.

        Returns:
            List of dicts with backend info.
        """
        result = []
        for name, backend in self._backends.items():
            healthy = self._backend_health.get(name, False)
            result.append({
                "name": name,
                "type": backend.config.get("type", "unknown"),
                "model": backend.config.get("model", "unknown"),
                "healthy": healthy,
                "requests": self._request_counts.get(name, 0),
                "tokens_used": backend._total_tokens_used,
            })
        return result

    def check_health(self):
        """Check health of all backends and update status.

        Returns:
            Dict mapping backend names to health check results.
        """
        results = {}
        for name, backend in self._backends.items():
            try:
                health = backend.health_check()
                self._backend_health[name] = health.get("available", False)
                results[name] = health
            except Exception as e:
                self._backend_health[name] = False
                results[name] = {
                    "available": False,
                    "message": str(e),
                }
        return results

    def refresh_backends(self):
        """Re-initialize backends from current configuration.

        Useful after configuration changes.
        """
        self._backends.clear()
        self._backend_health.clear()
        self._request_counts.clear()
        self._init_backends()
