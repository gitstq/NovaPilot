"""OpenAI-compatible API backend for NovaPilot.

Implements LLM communication using only urllib from the standard library.
Supports streaming responses, function calling, and token counting.
Works with any OpenAI-compatible API (OpenAI, Azure OpenAI, local proxies, etc.).
"""

import json
import ssl
import urllib.request
import urllib.error
from novapilot.llm.base import LLMBackend, LLMError


class OpenAIBackend(LLMBackend):
    """OpenAI-compatible API backend.

    Supports the OpenAI Chat Completions API format, which is also
    compatible with many third-party providers (Azure OpenAI, Together AI,
    Anyscale, local proxies like LiteLLM, etc.).
    """

    def __init__(self, name="openai", config=None):
        """Initialize OpenAI backend.

        Args:
            name: Backend identifier name.
            config: Dict with keys:
                - api_key (str): API key for authentication.
                - base_url (str): API base URL.
                - model (str): Model name (e.g., 'gpt-3.5-turbo').
                - temperature (float): Default sampling temperature.
                - max_tokens (int): Default max response tokens.
                - timeout (int): Request timeout in seconds.
                - organization (str): Optional organization ID.
        """
        super().__init__(name, config)
        self.api_key = self.config.get("api_key", "")
        self.base_url = self.config.get(
            "base_url", "https://api.openai.com/v1"
        ).rstrip("/")
        self.model = self.config.get("model", "gpt-3.5-turbo")
        self.timeout = self.config.get("timeout", 60)
        self.organization = self.config.get("organization", "")

    def _build_headers(self):
        """Build HTTP headers for API requests.

        Returns:
            Dict of HTTP headers.
        """
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }
        if self.organization:
            headers["OpenAI-Organization"] = self.organization
        return headers

    def _build_messages(self, prompt, system_prompt=None):
        """Build the messages array for the API request.

        Args:
            prompt: User prompt text.
            system_prompt: Optional system prompt.

        Returns:
            List of message dicts.
        """
        messages = []
        if system_prompt:
            messages.append({
                "role": "system",
                "content": system_prompt,
            })
        messages.append({
            "role": "user",
            "content": prompt,
        })
        return messages

    def _build_body(self, messages, temperature, max_tokens, stream=False,
                    functions=None):
        """Build the request body JSON.

        Args:
            messages: List of message dicts.
            temperature: Sampling temperature.
            max_tokens: Maximum response tokens.
            stream: Whether to stream the response.
            functions: Optional list of function definitions.

        Returns:
            Dict representing the request body.
        """
        body = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": stream,
        }
        if functions:
            body["functions"] = functions
        return body

    def _make_request(self, url, body, stream=False):
        """Make an HTTP POST request to the API.

        Args:
            url: Full API endpoint URL.
            body: Request body dict.
            stream: Whether to handle as a streaming response.

        Returns:
            For non-streaming: parsed JSON response dict.
            For streaming: urllib.request.Request object for iteration.

        Raises:
            LLMError: If the request fails.
        """
        headers = self._build_headers()
        data = json.dumps(body).encode("utf-8")

        req = urllib.request.Request(url, data=data, headers=headers,
                                     method="POST")

        # Create SSL context that doesn't verify (for compatibility)
        # In production, proper certificate verification should be used
        ssl_context = ssl.create_default_context()

        try:
            response = urllib.request.urlopen(
                req, timeout=self.timeout, context=ssl_context
            )
            return response
        except urllib.error.HTTPError as e:
            error_body = ""
            try:
                error_body = e.read().decode("utf-8", errors="replace")
            except Exception:
                pass

            try:
                error_data = json.loads(error_body)
                error_msg = error_data.get(
                    "error",
                    error_data.get("message", error_body)
                )
                if isinstance(error_msg, dict):
                    error_msg = error_msg.get("message", str(error_msg))
            except (json.JSONDecodeError, TypeError):
                error_msg = error_body or str(e)

            raise LLMError(
                f"HTTP {e.code}: {error_msg}",
                backend_name=self.name,
                status_code=e.code,
            )
        except urllib.error.URLError as e:
            raise LLMError(
                f"Connection error: {e.reason}",
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

    def _parse_response(self, response):
        """Parse a non-streaming API response.

        Args:
            response: urllib response object.

        Returns:
            Dict with 'content', 'usage', and 'model' keys.
        """
        body = response.read().decode("utf-8")
        data = json.loads(body)

        # Extract content from the response
        content = ""
        choices = data.get("choices", [])
        if choices:
            message = choices[0].get("message", {})
            content = message.get("content", "")

            # Check for function calls
            function_call = message.get("function_call")
            tool_calls = message.get("tool_calls")

        # Extract usage information
        usage = data.get("usage", {})
        total_tokens = usage.get("total_tokens", 0)
        self._total_tokens_used += total_tokens

        return {
            "content": content,
            "usage": {
                "prompt_tokens": usage.get("prompt_tokens", 0),
                "completion_tokens": usage.get("completion_tokens", 0),
                "total_tokens": total_tokens,
            },
            "model": data.get("model", self.model),
            "finish_reason": choices[0].get("finish_reason") if choices else None,
        }

    def complete(self, prompt, system_prompt=None, temperature=None,
                 max_tokens=None, functions=None, **kwargs):
        """Send a completion request to the OpenAI-compatible API.

        Args:
            prompt: User prompt text.
            system_prompt: Optional system prompt.
            temperature: Sampling temperature.
            max_tokens: Maximum response tokens.
            functions: Optional function definitions for function calling.
            **kwargs: Additional parameters (e.g., 'messages' for multi-turn).

        Returns:
            Dict with 'content', 'usage', and 'model' keys.

        Raises:
            LLMError: If the request fails.
        """
        temp = self._get_temperature(temperature)
        tokens = self._get_max_tokens(max_tokens)

        # Allow passing pre-built messages for multi-turn conversations
        if "messages" in kwargs:
            messages = kwargs["messages"]
        else:
            messages = self._build_messages(prompt, system_prompt)

        body = self._build_body(messages, temp, tokens, stream=False,
                                functions=functions)
        url = f"{self.base_url}/chat/completions"

        def do_request():
            response = self._make_request(url, body, stream=False)
            return self._parse_response(response)

        return self._retry_request(do_request)

    def stream(self, prompt, system_prompt=None, temperature=None,
               max_tokens=None, **kwargs):
        """Stream a completion response from the OpenAI-compatible API.

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

        if "messages" in kwargs:
            messages = kwargs["messages"]
        else:
            messages = self._build_messages(prompt, system_prompt)

        body = self._build_body(messages, temp, tokens, stream=True)
        url = f"{self.base_url}/chat/completions"

        def do_request():
            return self._make_request(url, body, stream=True)

        response = self._retry_request(do_request)

        # Process SSE (Server-Sent Events) stream
        buffer = ""
        total_tokens = 0

        try:
            while True:
                chunk = response.read(1024)
                if not chunk:
                    break

                buffer += chunk.decode("utf-8", errors="replace")
                lines = buffer.split("\n")
                buffer = lines[-1]  # Keep incomplete line in buffer

                for line in lines[:-1]:
                    line = line.strip()
                    if not line:
                        continue
                    if line == "data: [DONE]":
                        return

                    if line.startswith("data: "):
                        data_str = line[6:]
                        try:
                            data = json.loads(data_str)
                            choices = data.get("choices", [])
                            if choices:
                                delta = choices[0].get("delta", {})
                                content = delta.get("content", "")
                                if content:
                                    self._request_count += 1
                                    yield content
                        except json.JSONDecodeError:
                            continue
        except Exception as e:
            raise LLMError(
                f"Stream error: {e}",
                backend_name=self.name,
            )

    def list_models(self):
        """List available models from the API.

        Returns:
            List of model name strings.
        """
        url = f"{self.base_url}/models"
        headers = self._build_headers()
        req = urllib.request.Request(url, headers=headers, method="GET")

        try:
            ssl_context = ssl.create_default_context()
            response = urllib.request.urlopen(
                req, timeout=self.timeout, context=ssl_context
            )
            body = response.read().decode("utf-8")
            data = json.loads(body)
            models = data.get("data", [])
            return sorted([m.get("id", "") for m in models])
        except Exception as e:
            raise LLMError(
                f"Failed to list models: {e}",
                backend_name=self.name,
            )

    def health_check(self):
        """Check if the OpenAI API is accessible.

        Returns:
            Dict with 'available' (bool) and 'message' (str).
        """
        if not self.api_key:
            return {
                "available": False,
                "message": "API key not configured.",
            }

        try:
            models = self.list_models()
            return {
                "available": True,
                "message": f"Connected. {len(models)} models available.",
                "model_count": len(models),
            }
        except LLMError as e:
            return {
                "available": False,
                "message": str(e),
            }
        except Exception as e:
            return {
                "available": False,
                "message": f"Health check failed: {e}",
            }
