"""Ollama local model backend for NovaPilot.

Implements LLM communication with locally running Ollama models.
Supports model listing, streaming, and automatic service detection.
"""

import json
import ssl
import urllib.request
import urllib.error
from novapilot.llm.base import LLMBackend, LLMError


class OllamaBackend(LLMBackend):
    """Ollama local model backend.

    Communicates with a locally running Ollama server to use
    open-source models like LLaMA, Mistral, Gemma, etc.
    No API key required - fully local and private.
    """

    def __init__(self, name="ollama", config=None):
        """Initialize Ollama backend.

        Args:
            name: Backend identifier name.
            config: Dict with keys:
                - base_url (str): Ollama server URL (default: http://localhost:11434).
                - model (str): Model name (e.g., 'llama3', 'mistral').
                - temperature (float): Default sampling temperature.
                - max_tokens (int): Default max response tokens.
                - timeout (int): Request timeout in seconds.
        """
        super().__init__(name, config)
        self.base_url = self.config.get(
            "base_url", "http://localhost:11434"
        ).rstrip("/")
        self.model = self.config.get("model", "llama3")
        self.timeout = self.config.get("timeout", 120)

    def _make_request(self, endpoint, body=None, method="POST", stream=False):
        """Make an HTTP request to the Ollama server.

        Args:
            endpoint: API endpoint path (e.g., '/api/chat').
            body: Optional request body dict.
            method: HTTP method.
            stream: Whether to handle as streaming response.

        Returns:
            urllib response object.

        Raises:
            LLMError: If the request fails.
        """
        url = f"{self.base_url}{endpoint}"
        headers = {"Content-Type": "application/json"}
        data = None

        if body:
            data = json.dumps(body).encode("utf-8")

        req = urllib.request.Request(url, data=data, headers=headers,
                                     method=method)

        try:
            response = urllib.request.urlopen(req, timeout=self.timeout)
            return response
        except urllib.error.HTTPError as e:
            error_body = ""
            try:
                error_body = e.read().decode("utf-8", errors="replace")
            except Exception:
                pass

            raise LLMError(
                f"HTTP {e.code}: {error_body or e.reason}",
                backend_name=self.name,
                status_code=e.code,
            )
        except urllib.error.URLError as e:
            raise LLMError(
                f"Connection error: {e.reason}. "
                f"Is Ollama running at {self.base_url}?",
                backend_name=self.name,
            )
        except TimeoutError:
            raise LLMError(
                f"Request timed out after {self.timeout}s",
                backend_name=self.name,
            )
        except Exception as e:
            raise LLMError(
                f"Unexpected error: {e}",
                backend_name=self.name,
            )

    def _build_messages(self, prompt, system_prompt=None, messages=None):
        """Build messages in Ollama chat format.

        Args:
            prompt: User prompt text.
            system_prompt: Optional system prompt.
            messages: Optional pre-built messages list.

        Returns:
            List of message dicts in Ollama format.
        """
        if messages:
            ollama_messages = []
            for msg in messages:
                role = msg.get("role", "user")
                # Ollama uses 'system', 'user', 'assistant' roles
                if role == "system":
                    ollama_messages.append({
                        "role": "system",
                        "content": msg.get("content", ""),
                    })
                elif role in ("user", "assistant"):
                    ollama_messages.append({
                        "role": role,
                        "content": msg.get("content", ""),
                    })
            return ollama_messages

        ollama_messages = []
        if system_prompt:
            ollama_messages.append({
                "role": "system",
                "content": system_prompt,
            })
        ollama_messages.append({
            "role": "user",
            "content": prompt,
        })
        return ollama_messages

    def complete(self, prompt, system_prompt=None, temperature=None,
                 max_tokens=None, **kwargs):
        """Send a completion request to Ollama.

        Args:
            prompt: User prompt text.
            system_prompt: Optional system prompt.
            temperature: Sampling temperature.
            max_tokens: Maximum response tokens.
            **kwargs: Additional parameters (e.g., 'messages' for multi-turn).

        Returns:
            Dict with 'content', 'usage', and 'model' keys.

        Raises:
            LLMError: If the request fails.
        """
        temp = self._get_temperature(temperature)
        tokens = self._get_max_tokens(max_tokens)

        messages = self._build_messages(
            prompt, system_prompt, kwargs.get("messages")
        )

        body = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": temp,
                "num_predict": tokens,
            },
        }

        def do_request():
            response = self._make_request("/api/chat", body)
            return self._parse_response(response)

        return self._retry_request(do_request)

    def _parse_response(self, response):
        """Parse an Ollama chat response.

        Args:
            response: urllib response object.

        Returns:
            Dict with 'content', 'usage', and 'model' keys.
        """
        body = response.read().decode("utf-8")
        data = json.loads(body)

        content = data.get("message", {}).get("content", "")

        # Ollama provides evaluation counts
        eval_count = data.get("eval_count", 0)
        prompt_eval_count = data.get("prompt_eval_count", 0)
        total_tokens = eval_count + prompt_eval_count
        self._total_tokens_used += total_tokens

        return {
            "content": content,
            "usage": {
                "prompt_tokens": prompt_eval_count,
                "completion_tokens": eval_count,
                "total_tokens": total_tokens,
            },
            "model": data.get("model", self.model),
            "finish_reason": data.get("done_reason"),
        }

    def stream(self, prompt, system_prompt=None, temperature=None,
               max_tokens=None, **kwargs):
        """Stream a completion response from Ollama.

        Args:
            prompt: User prompt text.
            system_prompt: Optional system prompt.
            temperature: Sampling temperature.
            max_tokens: Maximum response tokens.
            **kwargs: Additional parameters.

        Yields:
            String chunks of the response.

        Raises:
            LLMError: If the request fails.
        """
        temp = self._get_temperature(temperature)
        tokens = self._get_max_tokens(max_tokens)

        messages = self._build_messages(
            prompt, system_prompt, kwargs.get("messages")
        )

        body = {
            "model": self.model,
            "messages": messages,
            "stream": True,
            "options": {
                "temperature": temp,
                "num_predict": tokens,
            },
        }

        def do_request():
            return self._make_request("/api/chat", body)

        response = self._retry_request(do_request)

        # Process newline-delimited JSON stream
        buffer = ""

        try:
            while True:
                chunk = response.read(1024)
                if not chunk:
                    break

                buffer += chunk.decode("utf-8", errors="replace")
                lines = buffer.split("\n")
                buffer = lines[-1]

                for line in lines[:-1]:
                    line = line.strip()
                    if not line:
                        continue

                    try:
                        data = json.loads(line)
                        content = data.get("message", {}).get("content", "")
                        if content:
                            yield content

                        if data.get("done", False):
                            return
                    except json.JSONDecodeError:
                        continue
        except Exception as e:
            raise LLMError(
                f"Stream error: {e}",
                backend_name=self.name,
            )

    def list_models(self):
        """List locally available Ollama models.

        Returns:
            List of model name strings.
        """
        response = self._make_request("/api/tags", method="GET")
        body = response.read().decode("utf-8")
        data = json.loads(body)

        models = data.get("models", [])
        return sorted([m.get("name", "") for m in models])

    def pull_model(self, model_name):
        """Pull (download) a model from the Ollama registry.

        Args:
            model_name: Name of the model to pull.

        Yields:
            Status strings during download.
        """
        body = {
            "name": model_name,
            "stream": True,
        }

        response = self._make_request("/api/pull", body)

        buffer = ""
        while True:
            chunk = response.read(1024)
            if not chunk:
                break

            buffer += chunk.decode("utf-8", errors="replace")
            lines = buffer.split("\n")
            buffer = lines[-1]

            for line in lines[:-1]:
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    status = data.get("status", "")
                    yield status
                except json.JSONDecodeError:
                    continue

    def is_running(self):
        """Check if the Ollama server is running and accessible.

        Returns:
            True if Ollama is running, False otherwise.
        """
        try:
            response = self._make_request("/", method="GET")
            response.read()
            return True
        except Exception:
            return False

    def health_check(self):
        """Check if the Ollama service is available.

        Returns:
            Dict with 'available' (bool) and 'message' (str).
        """
        if self.is_running():
            try:
                models = self.list_models()
                model_info = f", {len(models)} models available"
                current = f" (current: {self.model})"
                return {
                    "available": True,
                    "message": f"Ollama running at {self.base_url}"
                               f"{model_info}{current}.",
                    "models": models,
                }
            except Exception as e:
                return {
                    "available": True,
                    "message": f"Ollama running but error listing models: {e}",
                }
        else:
            return {
                "available": False,
                "message": f"Ollama not running at {self.base_url}. "
                           f"Start it with: ollama serve",
            }
