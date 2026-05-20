"""Chat engine for NovaPilot.

Manages multi-turn conversations with context window management,
system prompt templates, tool integration, and streaming output.
"""

import time
from novapilot.chat.history import ChatHistory
from novapilot.llm.base import LLMBackend


# Built-in system prompt templates
SYSTEM_PROMPTS = {
    "default": (
        "You are NovaPilot, a helpful AI assistant. "
        "Be concise and accurate in your responses."
    ),
    "coder": (
        "You are an expert programmer assistant. "
        "Write clean, efficient, well-documented code. "
        "Always explain your approach before writing code. "
        "Use best practices and design patterns."
    ),
    "analyst": (
        "You are a data analysis expert. "
        "Help users analyze data, create visualizations, "
        "and derive insights. Be thorough and precise."
    ),
    "writer": (
        "You are a skilled writing assistant. "
        "Help with creative writing, editing, and content creation. "
        "Adapt your style to match the user's needs."
    ),
    "tutor": (
        "You are a patient and knowledgeable tutor. "
        "Explain concepts clearly with examples. "
        "Adapt to the learner's level and pace."
    ),
}


class ChatEngine:
    """Multi-turn conversation engine with context management.

    Handles conversation flow, context window management,
    tool invocation, and response streaming.
    """

    def __init__(self, llm_router, config_manager=None, history=None):
        """Initialize ChatEngine.

        Args:
            llm_router: LLMRouter instance for backend selection.
            config_manager: Optional ConfigManager instance.
            history: Optional ChatHistory instance. Creates new one if None.
        """
        self.router = llm_router
        self.config_manager = config_manager
        self.history = history or ChatHistory()

        # Load chat configuration
        chat_config = {}
        if config_manager:
            chat_config = config_manager.get_chat_config()

        self.system_prompt = chat_config.get(
            "system_prompt", SYSTEM_PROMPTS["default"]
        )
        self.max_context_messages = chat_config.get(
            "max_context_messages", 20
        )
        self.max_context_tokens = chat_config.get(
            "max_context_tokens", 8000
        )

        # Tool registry
        self._tools = {}
        self._tool_enabled = {}

        # Conversation state
        self._session_id = None
        self._messages = []  # Full message history for context
        self._total_input_tokens = 0
        self._total_output_tokens = 0

    def register_tool(self, name, tool_instance, enabled=True):
        """Register a tool for use in conversations.

        Args:
            name: Tool identifier name.
            tool_instance: Tool object with execute() method.
            enabled: Whether the tool is initially enabled.
        """
        self._tools[name] = tool_instance
        self._tool_enabled[name] = enabled

    def enable_tool(self, name, enabled=True):
        """Enable or disable a registered tool.

        Args:
            name: Tool name.
            enabled: True to enable, False to disable.

        Raises:
            ValueError: If tool name is not registered.
        """
        if name not in self._tools:
            raise ValueError(f"Tool '{name}' is not registered.")
        self._tool_enabled[name] = enabled

    def list_tools(self):
        """List all registered tools with their status.

        Returns:
            List of dicts with tool name and enabled status.
        """
        return [
            {"name": name, "enabled": enabled}
            for name, enabled in self._tool_enabled.items()
        ]

    def set_system_prompt(self, prompt):
        """Set the system prompt.

        Args:
            prompt: System prompt text, or a key from SYSTEM_PROMPTS.
        """
        if prompt in SYSTEM_PROMPTS:
            self.system_prompt = SYSTEM_PROMPTS[prompt]
        else:
            self.system_prompt = prompt

    def new_session(self, title=None):
        """Start a new chat session.

        Args:
            title: Optional session title.

        Returns:
            New session ID string.
        """
        self._session_id = self.history.create_session(title=title)
        self._messages = []
        self._total_input_tokens = 0
        self._total_output_tokens = 0
        return self._session_id

    def load_session(self, session_id):
        """Load an existing chat session.

        Args:
            title: Session ID to load.

        Returns:
            True if successful, False if session not found.
        """
        if not self.history.set_current_session(session_id):
            return False
        self._session_id = session_id
        self._messages = self.history.get_messages(session_id)
        return True

    def _estimate_message_tokens(self, message):
        """Estimate tokens for a single message.

        Args:
            message: Message dict with 'role' and 'content'.

        Returns:
            Estimated token count.
        """
        from novapilot.llm.base import LLMBackend
        content = message.get("content", "")
        role = message.get("role", "")
        return LLMBackend.estimate_tokens(role + ": " + content)

    def _build_context(self, max_messages=None, max_tokens=None):
        """Build the context window from message history.

        Automatically trims messages to fit within the context limits.
        System prompt is always included.

        Args:
            max_messages: Maximum number of messages in context.
            max_tokens: Maximum token budget for context.

        Returns:
            List of message dicts for the API call.
        """
        max_msgs = max_messages or self.max_context_messages
        max_tok = max_tokens or self.max_context_tokens

        # Start with recent messages and work backwards
        context = []
        total_tokens = 0

        # Always include system prompt
        if self.system_prompt:
            sys_tokens = self._estimate_message_tokens(
                {"role": "system", "content": self.system_prompt}
            )
            total_tokens += sys_tokens

        # Add messages from most recent to oldest
        for msg in reversed(self._messages):
            if len(context) >= max_msgs:
                break

            msg_tokens = self._estimate_message_tokens(msg)
            if total_tokens + msg_tokens > max_tok:
                break

            context.insert(0, msg)
            total_tokens += msg_tokens

        return context

    def _check_tool_triggers(self, user_message):
        """Check if the user message should trigger any tools.

        Analyzes the message for patterns that indicate a tool should be used.

        Args:
            user_message: User message string.

        Returns:
            List of (tool_name, tool_args) tuples, or empty list.
        """
        triggers = []
        msg_lower = user_message.lower()

        for name, tool in self._tools.items():
            if not self._tool_enabled.get(name, False):
                continue

            # Check if tool has trigger patterns
            if hasattr(tool, "trigger_patterns"):
                for pattern in tool.trigger_patterns:
                    if pattern.lower() in msg_lower:
                        triggers.append((name, user_message))
                        break

        return triggers

    def _execute_tool(self, tool_name, tool_args):
        """Execute a tool and return its result.

        Args:
            tool_name: Name of the tool to execute.
            tool_args: Arguments to pass to the tool.

        Returns:
            Tool execution result string.
        """
        tool = self._tools.get(tool_name)
        if tool is None:
            return f"Error: Tool '{tool_name}' not found."

        try:
            if hasattr(tool, "execute"):
                result = tool.execute(tool_args)
                return str(result)
            elif callable(tool):
                result = tool(tool_args)
                return str(result)
            else:
                return f"Error: Tool '{tool_name}' is not callable."
        except Exception as e:
            return f"Error executing tool '{tool_name}': {e}"

    def send(self, message, stream=False, backend_name=None):
        """Send a user message and get a response.

        Handles tool triggering, context management, and response retrieval.

        Args:
            message: User message string.
            stream: Whether to stream the response.
            backend_name: Explicit backend name to use.

        Returns:
            If stream=False: Response dict with 'content', 'usage', etc.
            If stream=True: Generator yielding response chunks.
        """
        # Ensure we have a session
        if not self._session_id:
            self.new_session()

        # Add user message to history
        self._messages.append({
            "role": "user",
            "content": message,
        })
        self.history.add_message("user", message, self._session_id)

        # Check for tool triggers
        tool_results = self._check_tool_triggers(message)
        tool_context = ""
        if tool_results:
            for tool_name, tool_args in tool_results:
                result = self._execute_tool(tool_name, tool_args)
                tool_context += f"\n[Tool: {tool_name}]\n{result}\n"

        # Build context
        context = self._build_context()

        # Append tool results to the last user message if any
        if tool_context:
            context[-1]["content"] += tool_context

        if stream:
            return self._stream_response(context, backend_name)
        else:
            return self._get_response(context, backend_name)

    def _get_response(self, context, backend_name=None):
        """Get a complete response from the LLM.

        Args:
            context: Message context list.
            backend_name: Optional explicit backend name.

        Returns:
            Response dict with 'content', 'usage', 'backend', etc.
        """
        try:
            result = self.router.complete(
                prompt="",  # Messages are passed via context
                system_prompt=self.system_prompt,
                messages=context,
                backend_name=backend_name,
            )

            content = result.get("content", "")
            usage = result.get("usage", {})

            # Track token usage
            self._total_input_tokens += usage.get("prompt_tokens", 0)
            self._total_output_tokens += usage.get("completion_tokens", 0)

            # Save assistant message
            self._messages.append({
                "role": "assistant",
                "content": content,
            })
            self.history.add_message(
                "assistant", content, self._session_id,
                metadata={"backend": result.get("backend", "unknown")}
            )

            return result

        except Exception as e:
            error_msg = f"Error: {e}"
            self._messages.append({
                "role": "assistant",
                "content": error_msg,
            })
            self.history.add_message("assistant", error_msg, self._session_id)
            return {"content": error_msg, "error": True}

    def _stream_response(self, context, backend_name=None):
        """Stream a response from the LLM.

        Args:
            context: Message context list.
            backend_name: Optional explicit backend name.

        Yields:
            String chunks of the response.
        """
        full_response = ""

        try:
            for chunk in self.router.stream(
                prompt="",
                system_prompt=self.system_prompt,
                messages=context,
                backend_name=backend_name,
            ):
                full_response += chunk
                yield chunk

            # Save complete response
            self._messages.append({
                "role": "assistant",
                "content": full_response,
            })
            self.history.add_message(
                "assistant", full_response, self._session_id,
                metadata={"backend": "streaming"}
            )

        except Exception as e:
            error_msg = f"Error: {e}"
            yield error_msg
            self._messages.append({
                "role": "assistant",
                "content": error_msg,
            })
            self.history.add_message("assistant", error_msg, self._session_id)

    def get_stats(self):
        """Get conversation statistics.

        Returns:
            Dict with session info, message counts, and token usage.
        """
        return {
            "session_id": self._session_id,
            "message_count": len(self._messages),
            "total_input_tokens": self._total_input_tokens,
            "total_output_tokens": self._total_output_tokens,
            "tools_registered": len(self._tools),
            "tools_enabled": sum(1 for v in self._tool_enabled.values() if v),
        }

    def get_session_history(self, limit=None):
        """Get the current session's message history.

        Args:
            limit: Maximum number of messages to return.

        Returns:
            List of message dicts.
        """
        if limit:
            return self._messages[-limit:]
        return list(self._messages)
