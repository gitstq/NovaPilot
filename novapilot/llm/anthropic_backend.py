"""Anthropic Claude API backend for NovaPilot.

Implements LLM communication with Anthropic's Claude API using urllib.
Supports streaming responses and the Claude message format.
"""

import json
import ssl
import urllib.request
import urllib.error
from novapilot.llm.base import LLMBackend, LLMError


class AnthropicBackend(LLMBackend):
    """Anthropic Claude API backend.

    Supports Claude models via the Anthropic Messages API.
    Handles the Anthropic-specific request/response format including
    the 128K context window and system prompt separation.
    """

    # Claude model context window sizes (approximate)
    MODEL_CONTEXT = {
        "claude-3-opus-20240229": 200000,
        "claude-3-sonnet-20240229": 200000,
        "claude-3-haiku-20240307": 200000,
        "claude-3-5-sonnet-20241022": 200000,
        "claude-3-5-haiku-20241022": 200000,
    }

    def __init__(self, name="anthropic", config=None):
        """Initialize Anthropic backend.

        Args:
            name: Backend identifier name.
            config: Dict with keys:
                - api_key (str): Anthropic API key.
                - base_url (str): API base URL.
                - model (str): Model name (e.g., 'claude-3-haiku-20240307').
                - temperature (float): Default sampling temperature.
                - max_tokens (int): Default max response tokens.
                - timeout (int): Request timeout in seconds.
                - anthropic_version (str): API version header.
        """
        super().__init__(name, config)
        self.api_key = self.config.get("api_key", "")
        self.base_url = self.config.get(
            "base_url", "https://api.anthropic.com"
        ).rstrip("/")
        self.model = self.config.get("model", "claude-3-haiku-20240307")
        self.timeout = self.config.get("timeout", 120)
        self.anthropic_version = self.config.get(
            "anthropic_version", "2023-06-01"
        )

    def _build_headers(self):
        """Build HTTP headers for Anthropic API requests.

        Returns:
            Dict of HTTP headers.
        """
        return {
            "Content-Type": "application/json",
            "x-api-key": self.api_key,
            "anthropic-version": self.anthropic_version,
            "anthropic-dangerous-direct-browser-access": "true",
        }

    def _build_body(self, messages, system_prompt=None, temperature=None,
                    max_tokens=None, stream=False):
        """Build the request body for Anthropic Messages API.

        Args:
            messages: List of message dicts with 'role' and 'content'.
            system_prompt: Optional system prompt (sent separately in Anthropic API).
            temperature: Sampling temperature.
            max_tokens: Maximum response tokens.
            stream: Whether to stream the response.

        Returns:
            Dict representing the request body.
        """
        body = {
            "model": self.model,
            "messages": messages,
            "max_tokens": max_tokens,
            "stream": stream,
        }

        if system_prompt:
            body["system"] = system_prompt

        if temperature is not None:
            body["temperature"] = temperature

        return body

    def _convert_messages(self, prompt, system_prompt=None, messages=None):
        """Convert prompt/messages to Anthropic format.

        Anthropic API expects messages to start with 'user' role.
        System prompts are sent as a separate top-level field.

        Args:
            prompt: User prompt text (used if messages not provided).
            system_prompt: Optional system prompt.
            messages: Optional pre-built messages list.

        Returns:
            Tuple of (anthropic_messages_list, system_prompt_str).
        """
        if messages:
            # Filter out system messages (Anthropic handles them separately)
            anthropic_messages = []
            extracted_system = system_prompt or ""

            for msg in messages:
                if msg.get("role") == "system":
                    extracted_system = msg.get("content", "")
                else:
                    anthropic_messages.append({
                        "role": msg["role"],
                        "content": msg["content"],
                    })

            return anthropic_messages, extracted_system

        # Build from prompt
        anthropic_messages = [{
            "role": "user",
            "content": prompt,
        }]
        return anthropic_messages, system_prompt or ""

    def _make_request(self, url, body, stream=False):
        """Make an HTTP POST request to the Anthropic API.

        Args:
            url: Full API endpoint URL.
            body: Request body dict.
            stream: Whether to handle as streaming response.

        Returns:
            urllib response object.

        Raises:
            LLMError: If the request fails.
        """
        headers = self._build_headers()
        data = json.dumps(body).encode("utf-8")
        req = urllib.request.Request(url, data=data, headers=headers,
                                     method="POST")
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
                error_msg = error_data.get("error", {}).get(
                    "message", error_body
                )
            except (json.JSONDecodeError, TypeError, AttributeError):
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
        """Parse a non-streaming Anthropic API response.

        Args:
            response: urllib response object.

        Returns:
            Dict with 'content', 'usage', and 'model' keys.
        """
        body = response.read().decode("utf-8")
        data = json.loads(body)

        # Extract text content from response
        content = ""
        content_blocks = data.get("content", [])
        for block in content_blocks:
            if block.get("type") == "text":
                content += block.get("text", "")

        # Extract usage
        usage = data.get("usage", {})
        input_tokens = usage.get("input_tokens", 0)
        output_tokens = usage.get("output_tokens", 0)
        total_tokens = input_tokens + output_tokens
        self._total_tokens_used += total_tokens

        return {
            "content": content,
            "usage": {
                "prompt_tokens": input_tokens,
                "completion_tokens": output_tokens,
                "total_tokens": total_tokens,
            },
            "model": data.get("model", self.model),
            "finish_reason": data.get("stop_reason"),
        }

    def complete(self, prompt, system_prompt=None, temperature=None,
                 max_tokens=None, **kwargs):
        """Send a completion request to the Anthropic Claude API.

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

        messages, sys_prompt = self._convert_messages(
            prompt, system_prompt, kwargs.get("messages")
        )

        body = self._build_body(
            messages, system_prompt=sys_prompt,
            temperature=temp, max_tokens=tokens, stream=False
        )
        url = f"{self.base_url}/v1/messages"

        def do_request():
            response = self._make_request(url, body, stream=False)
            return self._parse_response(response)

        return self._retry_request(do_request)

    def stream(self, prompt, system_prompt=None, temperature=None,
               max_tokens=None, **kwargs):
        """Stream a completion response from the Anthropic Claude API.

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

        messages, sys_prompt = self._convert_messages(
            prompt, system_prompt, kwargs.get("messages")
        )

        body = self._build_body(
            messages, system_prompt=sys_prompt,
            temperature=temp, max_tokens=tokens, stream=True
        )
        url = f"{self.base_url}/v1/messages"

        def do_request():
            return self._make_request(url, body, stream=True)

        response = self._retry_request(do_request)

        # Process SSE stream
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

                    if line.startswith("data: "):
                        data_str = line[6:]
                        try:
                            data = json.loads(data_str)

                            event_type = data.get("type", "")

                            if event_type == "content_block_delta":
                                delta = data.get("delta", {})
                                if delta.get("type") == "text_delta":
                                    text = delta.get("text", "")
                                    if text:
                                        yield text

                            elif event_type == "message_stop":
                                return

                            elif event_type == "error":
                                error = data.get("error", {})
                                raise LLMError(
                                    error.get("message", "Stream error"),
                                    backend_name=self.name,
                                )

                        except json.JSONDecodeError:
                            continue
                        except LLMError:
                            raise
                        except Exception:
                            continue
        except LLMError:
            raise
        except Exception as e:
            raise LLMError(
                f"Stream error: {e}",
                backend_name=self.name,
            )

    def get_context_window(self):
        """Get the context window size for the configured model.

        Returns:
            Context window size in tokens (int).
        """
        return self.MODEL_CONTEXT.get(self.model, 128000)

    def health_check(self):
        """Check if the Anthropic API is accessible.

        Returns:
            Dict with 'available' (bool) and 'message' (str).
        """
        if not self.api_key:
            return {
                "available": False,
                "message": "API key not configured.",
            }

        try:
            # Send a minimal request to test connectivity
            result = self.complete(
                "Hi",
                max_tokens=10,
            )
            return {
                "available": True,
                "message": f"Connected. Model: {result.get('model', 'unknown')}.",
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
