"""Configuration management for NovaPilot.

Handles loading, saving, and managing LLM backend configurations.
Configuration is stored in JSON format at ~/.novapilot/config.json.
"""

import json
import os
import copy

# Default configuration template
DEFAULT_CONFIG = {
    "version": "0.1.0",
    "default_backend": "openai",
    "backends": {
        "openai": {
            "type": "openai",
            "api_key": "",
            "base_url": "https://api.openai.com/v1",
            "model": "gpt-3.5-turbo",
            "temperature": 0.7,
            "max_tokens": 4096,
            "enabled": True,
        },
        "anthropic": {
            "type": "anthropic",
            "api_key": "",
            "base_url": "https://api.anthropic.com",
            "model": "claude-3-haiku-20240307",
            "temperature": 0.7,
            "max_tokens": 4096,
            "enabled": False,
        },
        "ollama": {
            "type": "ollama",
            "base_url": "http://localhost:11434",
            "model": "llama3",
            "temperature": 0.7,
            "max_tokens": 4096,
            "enabled": False,
        },
    },
    "memory": {
        "enabled": True,
        "max_memories": 10000,
        "auto_save": True,
    },
    "tools": {
        "code_analyzer": {"enabled": True},
        "file_manager": {"enabled": True},
        "web_search": {"enabled": True},
        "calculator": {"enabled": True},
    },
    "chat": {
        "system_prompt": "You are NovaPilot, a helpful AI assistant. "
                         "Be concise and accurate in your responses.",
        "max_context_messages": 20,
        "max_context_tokens": 8000,
    },
    "tui": {
        "theme": "dark",
        "color_enabled": True,
    },
}

# Directory and file paths for NovaPilot data
NOVAPILOT_DIR = os.path.join(os.path.expanduser("~"), ".novapilot")
CONFIG_PATH = os.path.join(NOVAPILOT_DIR, "config.json")
HISTORY_DIR = os.path.join(NOVAPILOT_DIR, "history")
MEMORY_PATH = os.path.join(NOVAPILOT_DIR, "memory.json")
LOG_PATH = os.path.join(NOVAPILOT_DIR, "novapilot.log")


def _ensure_dirs():
    """Ensure all required directories exist."""
    for directory in [NOVAPILOT_DIR, HISTORY_DIR]:
        os.makedirs(directory, exist_ok=True)


class ConfigManager:
    """Manages NovaPilot configuration.

    Handles loading configuration from disk, merging with defaults,
    and saving changes. Supports multiple LLM backend configurations.
    """

    def __init__(self, config_path=None):
        """Initialize ConfigManager.

        Args:
            config_path: Optional custom path to config file.
                         Defaults to ~/.novapilot/config.json.
        """
        self.config_path = config_path or CONFIG_PATH
        self._config = None
        _ensure_dirs()
        self.load()

    def load(self):
        """Load configuration from disk, merging with defaults.

        If no config file exists, creates one with default values.
        Missing keys in existing config are filled from defaults.
        """
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    user_config = json.load(f)
                self._config = self._merge_config(
                    copy.deepcopy(DEFAULT_CONFIG), user_config
                )
            except (json.JSONDecodeError, IOError) as e:
                self._config = copy.deepcopy(DEFAULT_CONFIG)
        else:
            self._config = copy.deepcopy(DEFAULT_CONFIG)
            self.save()

    def save(self):
        """Save current configuration to disk.

        Creates parent directories if they don't exist.
        """
        _ensure_dirs()
        try:
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(self._config, f, indent=2, ensure_ascii=False)
        except IOError as e:
            raise IOError(f"Failed to save config to {self.config_path}: {e}")

    def _merge_config(self, default, user):
        """Recursively merge user config into default config.

        Args:
            default: Default configuration dict.
            user: User configuration dict.

        Returns:
            Merged configuration dict.
        """
        merged = copy.deepcopy(default)
        for key, value in user.items():
            if key in merged and isinstance(merged[key], dict) and isinstance(value, dict):
                merged[key] = self._merge_config(merged[key], value)
            else:
                merged[key] = copy.deepcopy(value)
        return merged

    @property
    def config(self):
        """Get the full configuration dictionary."""
        return copy.deepcopy(self._config)

    @property
    def default_backend(self):
        """Get the name of the default LLM backend."""
        return self._config.get("default_backend", "openai")

    @default_backend.setter
    def default_backend(self, name):
        """Set the default LLM backend.

        Args:
            name: Name of the backend to set as default.
        """
        if name in self._config.get("backends", {}):
            self._config["default_backend"] = name
            self.save()
        else:
            available = list(self._config.get("backends", {}).keys())
            raise ValueError(
                f"Unknown backend '{name}'. Available: {available}"
            )

    def get_backend(self, name):
        """Get configuration for a specific backend.

        Args:
            name: Backend name (e.g., 'openai', 'anthropic', 'ollama').

        Returns:
            Dict containing backend configuration, or None if not found.
        """
        backends = self._config.get("backends", {})
        return copy.deepcopy(backends.get(name))

    def list_backends(self):
        """List all configured backends with their status.

        Returns:
            List of dicts with backend name, type, model, and enabled status.
        """
        result = []
        for name, cfg in self._config.get("backends", {}).items():
            result.append({
                "name": name,
                "type": cfg.get("type", "unknown"),
                "model": cfg.get("model", "unknown"),
                "enabled": cfg.get("enabled", False),
                "has_api_key": bool(cfg.get("api_key", "")),
            })
        return result

    def add_backend(self, name, backend_type, **kwargs):
        """Add or update a backend configuration.

        Args:
            name: Unique name for the backend.
            backend_type: Type of backend ('openai', 'anthropic', 'ollama').
            **kwargs: Additional configuration parameters (api_key, model, etc.).
        """
        if "backends" not in self._config:
            self._config["backends"] = {}

        # Start with type-specific defaults
        type_defaults = {}
        if backend_type == "openai":
            type_defaults = {
                "type": "openai",
                "api_key": "",
                "base_url": "https://api.openai.com/v1",
                "model": "gpt-3.5-turbo",
                "temperature": 0.7,
                "max_tokens": 4096,
                "enabled": True,
            }
        elif backend_type == "anthropic":
            type_defaults = {
                "type": "anthropic",
                "api_key": "",
                "base_url": "https://api.anthropic.com",
                "model": "claude-3-haiku-20240307",
                "temperature": 0.7,
                "max_tokens": 4096,
                "enabled": True,
            }
        elif backend_type == "ollama":
            type_defaults = {
                "type": "ollama",
                "base_url": "http://localhost:11434",
                "model": "llama3",
                "temperature": 0.7,
                "max_tokens": 4096,
                "enabled": True,
            }
        else:
            raise ValueError(f"Unknown backend type: {backend_type}")

        # Merge user-provided kwargs
        type_defaults.update(kwargs)
        self._config["backends"][name] = type_defaults
        self.save()

    def remove_backend(self, name):
        """Remove a backend configuration.

        Args:
            name: Name of the backend to remove.

        Raises:
            ValueError: If attempting to remove the last backend.
        """
        backends = self._config.get("backends", {})
        if name not in backends:
            raise ValueError(f"Backend '{name}' not found.")

        if len(backends) <= 1:
            raise ValueError("Cannot remove the last backend.")

        del self._config["backends"][name]

        # Reset default if needed
        if self._config.get("default_backend") == name:
            self._config["default_backend"] = list(backends.keys())[0]

        self.save()

    def set_backend_config(self, name, **kwargs):
        """Update specific fields of a backend configuration.

        Args:
            name: Backend name.
            **kwargs: Fields to update.
        """
        if name not in self._config.get("backends", {}):
            raise ValueError(f"Backend '{name}' not found.")

        self._config["backends"][name].update(kwargs)
        self.save()

    def get_tool_config(self, tool_name):
        """Get configuration for a specific tool.

        Args:
            tool_name: Name of the tool.

        Returns:
            Tool configuration dict, or default enabled config if not found.
        """
        tools = self._config.get("tools", {})
        if tool_name in tools:
            return copy.deepcopy(tools[tool_name])
        return {"enabled": True}

    def set_tool_enabled(self, tool_name, enabled):
        """Enable or disable a tool.

        Args:
            tool_name: Name of the tool.
            enabled: True to enable, False to disable.
        """
        if "tools" not in self._config:
            self._config["tools"] = {}
        if tool_name not in self._config["tools"]:
            self._config["tools"][tool_name] = {}
        self._config["tools"][tool_name]["enabled"] = enabled
        self.save()

    def list_tools(self):
        """List all tools with their enabled status.

        Returns:
            Dict mapping tool names to their enabled status.
        """
        return copy.deepcopy(self._config.get("tools", {}))

    def get_chat_config(self):
        """Get chat-related configuration.

        Returns:
            Dict with chat configuration (system_prompt, max_context_messages, etc.).
        """
        return copy.deepcopy(self._config.get("chat", {}))

    def set_chat_config(self, **kwargs):
        """Update chat configuration.

        Args:
            **kwargs: Chat config fields to update.
        """
        if "chat" not in self._config:
            self._config["chat"] = {}
        self._config["chat"].update(kwargs)
        self.save()

    def get_memory_config(self):
        """Get memory-related configuration.

        Returns:
            Dict with memory configuration.
        """
        return copy.deepcopy(self._config.get("memory", {}))

    def get_tui_config(self):
        """Get TUI-related configuration.

        Returns:
            Dict with TUI configuration (theme, color_enabled, etc.).
        """
        return copy.deepcopy(self._config.get("tui", {}))

    def reset(self):
        """Reset configuration to defaults."""
        self._config = copy.deepcopy(DEFAULT_CONFIG)
        self.save()

    def export_config(self):
        """Export configuration as a JSON string.

        Returns:
            Pretty-printed JSON string of current configuration.
        """
        return json.dumps(self._config, indent=2, ensure_ascii=False)
