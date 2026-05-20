"""Abstract base class for LLM backends.

All LLM backend implementations must inherit from LLMBackend
and implement the complete() and stream() methods.
"""

import json
import time
import threading
from abc import ABC, abstractmethod


class LLMError(Exception):
    """Custom exception for LLM-related errors."""

    def __init__(self, message, backend_name="", status_code=None):
        """Initialize LLMError.

        Args:
            message: Error description.
            backend_name: Name of the backend that caused the error.
            status_code: HTTP status code if applicable.
        """
        self.backend_name = backend_name
        self.status_code = status_code
        super().__init__(f"[{backend_name}] {message}" if backend_name else message)


class LLMBackend(ABC):
    """Abstract base class for LLM backend implementations.

    Provides common functionality like retry logic, token estimation,
    and error handling. Subclasses must implement complete() and stream().
    """

    # Maximum number of retry attempts for transient errors
    MAX_RETRIES = 3
    # Base delay between retries in seconds (exponential backoff)
    RETRY_BASE_DELAY = 1.0
    # HTTP status codes that should trigger a retry
    RETRY_STATUS_CODES = {429, 500, 502, 503, 504}

    def __init__(self, name, config=None):
        """Initialize LLMBackend.

        Args:
            name: Human-readable name for this backend.
            config: Dict containing backend configuration.
        """
        self.name = name
        self.config = config or {}
        self._request_count = 0
        self._total_tokens_used = 0
        self._last_error = None

    @abstractmethod
    def complete(self, prompt, system_prompt=None, temperature=None,
                 max_tokens=None, **kwargs):
        """Send a completion request to the LLM.

        Args:
            prompt: User prompt text.
            system_prompt: Optional system prompt.
            temperature: Sampling temperature (0.0-2.0).
            max_tokens: Maximum tokens in response.
            **kwargs: Additional backend-specific parameters.

        Returns:
            Dict with 'content' (str), 'usage' (dict with token counts),
            and 'model' (str) keys.

        Raises:
            LLMError: If the request fails after retries.
        """
        pass

    @abstractmethod
    def stream(self, prompt, system_prompt=None, temperature=None,
               max_tokens=None, **kwargs):
        """Stream a completion response from the LLM.

        Args:
            prompt: User prompt text.
            system_prompt: Optional system prompt.
            temperature: Sampling temperature (0.0-2.0).
            max_tokens: Maximum tokens in response.
            **kwargs: Additional backend-specific parameters.

        Yields:
            String chunks of the response as they arrive.

        Raises:
            LLMError: If the request fails after retries.
        """
        pass

    def _get_temperature(self, temperature):
        """Get temperature value, using config default if not specified.

        Args:
            temperature: User-specified temperature, or None for default.

        Returns:
            Temperature float value.
        """
        if temperature is not None:
            return max(0.0, min(2.0, float(temperature)))
        return float(self.config.get("temperature", 0.7))

    def _get_max_tokens(self, max_tokens):
        """Get max_tokens value, using config default if not specified.

        Args:
            max_tokens: User-specified max_tokens, or None for default.

        Returns:
            Max tokens integer value.
        """
        if max_tokens is not None:
            return max(1, int(max_tokens))
        return int(self.config.get("max_tokens", 4096))

    def _retry_request(self, request_func, *args, **kwargs):
        """Execute a request with exponential backoff retry logic.

        Args:
            request_func: Callable that performs the actual request.
            *args: Positional arguments for request_func.
            **kwargs: Keyword arguments for request_func.

        Returns:
            Result from request_func.

        Raises:
            LLMError: If all retry attempts fail.
        """
        last_exception = None

        for attempt in range(self.MAX_RETRIES):
            try:
                result = request_func(*args, **kwargs)
                self._request_count += 1
                return result
            except LLMError as e:
                last_exception = e
                self._last_error = str(e)
                if e.status_code and e.status_code not in self.RETRY_STATUS_CODES:
                    raise
                if attempt < self.MAX_RETRIES - 1:
                    delay = self.RETRY_BASE_DELAY * (2 ** attempt)
                    time.sleep(delay)
            except Exception as e:
                last_exception = e
                self._last_error = str(e)
                if attempt < self.MAX_RETRIES - 1:
                    delay = self.RETRY_BASE_DELAY * (2 ** attempt)
                    time.sleep(delay)

        raise LLMError(
            f"Request failed after {self.MAX_RETRIES} attempts: {last_exception}",
            backend_name=self.name,
        )

    @staticmethod
    def estimate_tokens(text):
        """Estimate the number of tokens in a text string.

        Uses a simple heuristic: ~4 characters per token for English,
        ~2 characters per token for CJK text.

        Args:
            text: Input text string.

        Returns:
            Estimated token count (int).
        """
        if not text:
            return 0

        total_chars = len(text)
        # Count CJK characters (rough heuristic)
        cjk_count = 0
        for char in text:
            cp = ord(char)
            if (0x4E00 <= cp <= 0x9FFF or
                0x3400 <= cp <= 0x4DBF or
                0x20000 <= cp <= 0x2A6DF or
                0xF900 <= cp <= 0xFAFF or
                0x2F800 <= cp <= 0x2FA1F or
                0x3000 <= cp <= 0x303F or
                0xFF00 <= cp <= 0xFFEF):
                cjk_count += 1

        non_cjk_count = total_chars - cjk_count
        # CJK: ~1.5 chars per token, Non-CJK: ~4 chars per token
        estimated = int(cjk_count / 1.5 + non_cjk_count / 4.0)
        return max(1, estimated)

    @property
    def stats(self):
        """Get usage statistics for this backend.

        Returns:
            Dict with request_count and total_tokens_used.
        """
        return {
            "backend": self.name,
            "request_count": self._request_count,
            "total_tokens_used": self._total_tokens_used,
        }

    def health_check(self):
        """Check if the backend is available and properly configured.

        Returns:
            Dict with 'available' (bool) and 'message' (str) keys.
        """
        return {
            "available": False,
            "message": "Health check not implemented for this backend.",
        }

    def __repr__(self):
        """String representation of the backend.

        Returns:
            Backend name and type string.
        """
        return f"<{self.__class__.__name__}(name='{self.name}')>"
