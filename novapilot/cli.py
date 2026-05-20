"""Command-line interface for NovaPilot.

Provides the main entry point with argparse-based subcommands for
chat, config management, memory management, tool management,
and TUI dashboard launch.
"""

import argparse
import sys
import os

from novapilot import __version__
from novapilot.config import ConfigManager
from novapilot.utils.logger import get_logger, Colors
from novapilot.utils.formatter import Formatter


def create_parser():
    """Create the argument parser with all subcommands.

    Returns:
        Configured argparse.ArgumentParser instance.
    """
    parser = argparse.ArgumentParser(
        prog="novapilot",
        description="NovaPilot - Lightweight Terminal AI Personal Super Intelligence Engine",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  novapilot chat                    Start interactive chat\n"
            "  novapilot config list             List configured backends\n"
            "  novapilot config add openai       Add OpenAI backend\n"
            "  novapilot memory search 'query'   Search memories\n"
            "  novapilot dashboard               Launch TUI dashboard\n"
        ),
    )

    parser.add_argument(
        "--version", "-v",
        action="version",
        version=f"NovaPilot v{__version__}",
    )

    # Global options
    parser.add_argument(
        "--config", "-c",
        default=None,
        help="Path to custom config file",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        default=False,
        help="Enable verbose output",
    )
    parser.add_argument(
        "--no-color",
        action="store_true",
        default=False,
        help="Disable colored output",
    )

    # Subcommands
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # ── chat subcommand ────────────────────────────────────────────────
    chat_parser = subparsers.add_parser(
        "chat", help="Start interactive chat session"
    )
    chat_parser.add_argument(
        "--backend", "-b",
        default=None,
        help="Use specific LLM backend",
    )
    chat_parser.add_argument(
        "--system-prompt", "-s",
        default=None,
        help="Custom system prompt",
    )
    chat_parser.add_argument(
        "--session", "-S",
        default=None,
        help="Resume a specific session ID",
    )
    chat_parser.add_argument(
        "--prompt", "-p",
        default=None,
        help="Send a single prompt and exit (non-interactive)",
    )

    # ── config subcommand ──────────────────────────────────────────────
    config_parser = subparsers.add_parser(
        "config", help="Manage LLM backend configuration"
    )
    config_sub = config_parser.add_subparsers(dest="config_action")

    # config list
    config_sub.add_parser("list", help="List all configured backends")

    # config add
    config_add = config_sub.add_parser("add", help="Add a new backend")
    config_add.add_argument("name", help="Backend name")
    config_add.add_argument(
        "--type", "-t",
        required=True,
        choices=["openai", "anthropic", "ollama"],
        help="Backend type",
    )
    config_add.add_argument("--api-key", default=None, help="API key")
    config_add.add_argument("--base-url", default=None, help="Base URL")
    config_add.add_argument("--model", default=None, help="Model name")
    config_add.add_argument("--temperature", type=float, default=None)
    config_add.add_argument("--max-tokens", type=int, default=None)

    # config remove
    config_remove = config_sub.add_parser("remove", help="Remove a backend")
    config_remove.add_argument("name", help="Backend name to remove")

    # config set-default
    config_default = config_sub.add_parser(
        "set-default", help="Set default backend"
    )
    config_default.add_argument("name", help="Backend name to set as default")

    # config test
    config_test = config_sub.add_parser("test", help="Test backend connectivity")
    config_test.add_argument("name", nargs="?", default=None, help="Backend name (all if omitted)")

    # config show
    config_show = config_sub.add_parser("show", help="Show full configuration")
    config_show.add_argument("--raw", action="store_true", help="Show raw JSON")

    # config reset
    config_sub.add_parser("reset", help="Reset configuration to defaults")

    # ── memory subcommand ──────────────────────────────────────────────
    memory_parser = subparsers.add_parser(
        "memory", help="Manage memory store"
    )
    memory_sub = memory_parser.add_subparsers(dest="memory_action")

    # memory list
    memory_list = memory_sub.add_parser("list", help="List memories")
    memory_list.add_argument("--category", default=None, help="Filter by category")
    memory_list.add_argument("--limit", type=int, default=20, help="Max entries")

    # memory search
    memory_search = memory_sub.add_parser("search", help="Search memories")
    memory_search.add_argument("query", help="Search query")

    # memory add
    memory_add = memory_sub.add_parser("add", help="Add a memory")
    memory_add.add_argument("content", help="Memory content")
    memory_add.add_argument("--category", default="general", help="Memory category")
    memory_add.add_argument("--tags", default=None, help="Comma-separated tags")

    # memory clear
    memory_clear = memory_sub.add_parser("clear", help="Clear memories")
    memory_clear.add_argument(
        "--category", default=None,
        help="Clear only this category (omit for all)"
    )

    # memory export
    memory_export = memory_sub.add_parser("export", help="Export memories")
    memory_export.add_argument(
        "--format", "-f",
        default="json",
        choices=["json", "jsonl"],
        help="Export format",
    )
    memory_export.add_argument(
        "--output", "-o",
        default=None,
        help="Output file path (stdout if omitted)",
    )

    # memory stats
    memory_sub.add_parser("stats", help="Show memory statistics")

    # ── tools subcommand ───────────────────────────────────────────────
    tools_parser = subparsers.add_parser(
        "tools", help="Manage built-in tools"
    )
    tools_sub = tools_parser.add_subparsers(dest="tools_action")

    # tools list
    tools_sub.add_parser("list", help="List available tools")

    # tools enable
    tools_enable = tools_sub.add_parser("enable", help="Enable a tool")
    tools_enable.add_argument("name", help="Tool name")

    # tools disable
    tools_disable = tools_sub.add_parser("disable", help="Disable a tool")
    tools_disable.add_argument("name", help="Tool name")

    # ── dashboard subcommand ───────────────────────────────────────────
    dash_parser = subparsers.add_parser(
        "dashboard", help="Launch TUI dashboard"
    )
    dash_parser.add_argument(
        "--theme", "-t",
        default=None,
        choices=["dark", "light"],
        help="Color theme",
    )

    return parser


def cmd_config(args, config, formatter, logger):
    """Handle config subcommand.

    Args:
        args: Parsed arguments.
        config: ConfigManager instance.
        formatter: Formatter instance.
        logger: Logger instance.
    """
    action = args.config_action

    if action == "list":
        backends = config.list_backends()
        if not backends:
            print(formatter.info("No backends configured."))
            return

        headers = ["Name", "Type", "Model", "Enabled", "API Key"]
        rows = []
        for b in backends:
            rows.append([
                b["name"],
                b["type"],
                b["model"],
                "Yes" if b["enabled"] else "No",
                "Set" if b["has_api_key"] else "Missing",
            ])
        print(formatter.render_table(headers, rows))

    elif action == "add":
        kwargs = {}
        if args.api_key:
            kwargs["api_key"] = args.api_key
        if args.base_url:
            kwargs["base_url"] = args.base_url
        if args.model:
            kwargs["model"] = args.model
        if args.temperature is not None:
            kwargs["temperature"] = args.temperature
        if args.max_tokens is not None:
            kwargs["max_tokens"] = args.max_tokens

        try:
            config.add_backend(args.name, args.type, **kwargs)
            print(formatter.success(f"Backend '{args.name}' added successfully."))
        except ValueError as e:
            print(formatter.error(str(e)))

    elif action == "remove":
        try:
            config.remove_backend(args.name)
            print(formatter.success(f"Backend '{args.name}' removed."))
        except ValueError as e:
            print(formatter.error(str(e)))

    elif action == "set-default":
        try:
            config.default_backend = args.name
            print(formatter.success(f"Default backend set to '{args.name}'."))
        except ValueError as e:
            print(formatter.error(str(e)))

    elif action == "test":
        from novapilot.llm.router import LLMRouter
        router = LLMRouter(config)

        if args.name:
            backend = router.get_backend(args.name)
            if backend:
                print(f"Testing backend: {args.name}")
                result = backend.health_check()
                if result["available"]:
                    print(formatter.success(result["message"]))
                else:
                    print(formatter.error(result["message"]))
            else:
                print(formatter.error(f"Backend '{args.name}' not found."))
        else:
            print("Testing all backends...")
            results = router.check_health()
            for name, result in results.items():
                if result["available"]:
                    print(formatter.success(f"  {name}: {result['message']}"))
                else:
                    print(formatter.error(f"  {name}: {result['message']}"))

    elif action == "show":
        if args.raw:
            print(config.export_config())
        else:
            print(formatter.render_key_value(config.config))

    elif action == "reset":
        config.reset()
        print(formatter.success("Configuration reset to defaults."))

    else:
        print("Usage: novapilot config {list|add|remove|set-default|test|show|reset}")


def cmd_memory(args, config, formatter, logger):
    """Handle memory subcommand.

    Args:
        args: Parsed arguments.
        config: ConfigManager instance.
        formatter: Formatter instance.
        logger: Logger instance.
    """
    from novapilot.memory.engine import MemoryEngine

    action = args.memory_action
    engine = MemoryEngine()

    if action == "list":
        memories = engine.list_memories(
            category=args.category,
            limit=args.limit,
        )
        if not memories:
            print(formatter.info("No memories stored."))
            return

        headers = ["ID", "Category", "Tags", "Content", "Created"]
        rows = []
        for m in memories:
            content = m.get("content", "")[:50] + "..." if len(m.get("content", "")) > 50 else m.get("content", "")
            tags = ", ".join(m.get("tags", [])[:3])
            rows.append([
                m.get("id", ""),
                m.get("category", "general"),
                tags,
                content,
                m.get("created_at", "")[:10],
            ])
        print(formatter.render_table(headers, rows))

    elif action == "search":
        results = engine.recall(args.query, top_k=5)
        if not results:
            print(formatter.info(f"No memories matching '{args.query}'."))
            return

        for r in results:
            entry = r["entry"]
            print(f"\n{formatter.bold(entry.get('id', ''))} "
                  f"(score: {r['score']}, {entry.get('category', 'general')})")
            content = entry.get("content", "")
            print(f"  {content[:200]}{'...' if len(content) > 200 else ''}")
            if entry.get("tags"):
                print(f"  Tags: {', '.join(entry['tags'])}")

    elif action == "add":
        tags = args.tags.split(",") if args.tags else []
        entry_id = engine.remember(
            content=args.content,
            category=args.category,
            tags=tags,
        )
        print(formatter.success(f"Memory saved: {entry_id}"))

    elif action == "clear":
        count = engine.clear(category=args.category)
        if args.category:
            print(formatter.success(f"Cleared {count} memories in '{args.category}'."))
        else:
            print(formatter.success(f"Cleared all {count} memories."))

    elif action == "export":
        data = engine.export_memories(format_type=args.format)
        if args.output:
            try:
                with open(args.output, "w", encoding="utf-8") as f:
                    f.write(data)
                print(formatter.success(f"Exported to {args.output}"))
            except IOError as e:
                print(formatter.error(f"Failed to write: {e}"))
        else:
            print(data)

    elif action == "stats":
        stats = engine.get_stats()
        print(formatter.render_key_value(stats))

    else:
        print("Usage: novapilot memory {list|search|add|clear|export|stats}")


def cmd_tools(args, config, formatter, logger):
    """Handle tools subcommand.

    Args:
        args: Parsed arguments.
        config: ConfigManager instance.
        formatter: Formatter instance.
        logger: Logger instance.
    """
    action = args.tools_action

    if action == "list":
        tools = config.list_tools()
        if not tools:
            print(formatter.info("No tools configured."))
            return

        headers = ["Tool", "Enabled"]
        rows = [
            [name, "Yes" if cfg.get("enabled", True) else "No"]
            for name, cfg in tools.items()
        ]
        print(formatter.render_table(headers, rows))

    elif action == "enable":
        config.set_tool_enabled(args.name, True)
        print(formatter.success(f"Tool '{args.name}' enabled."))

    elif action == "disable":
        config.set_tool_enabled(args.name, False)
        print(formatter.success(f"Tool '{args.name}' disabled."))

    else:
        print("Usage: novapilot tools {list|enable|disable}")


def cmd_chat(args, config, formatter, logger):
    """Handle chat subcommand.

    Args:
        args: Parsed arguments.
        config: ConfigManager instance.
        formatter: Formatter instance.
        logger: Logger instance.
    """
    from novapilot.llm.router import LLMRouter
    from novapilot.chat.engine import ChatEngine
    from novapilot.tools.code_analyzer import CodeAnalyzer
    from novapilot.tools.file_manager import FileManager
    from novapilot.tools.web_search import WebSearch
    from novapilot.tools.calculator import Calculator

    # Initialize router and chat engine
    router = LLMRouter(config)
    chat = ChatEngine(llm_router=router, config_manager=config)

    # Register tools
    tool_configs = config.list_tools()
    tools_map = {
        "code_analyzer": CodeAnalyzer(),
        "file_manager": FileManager(),
        "web_search": WebSearch(),
        "calculator": Calculator(),
    }

    for name, tool in tools_map.items():
        enabled = tool_configs.get(name, {}).get("enabled", True)
        chat.register_tool(name, tool, enabled=enabled)

    # Set system prompt
    if args.system_prompt:
        chat.set_system_prompt(args.system_prompt)

    # Load session if specified
    if args.session:
        if not chat.load_session(args.session):
            print(formatter.error(f"Session '{args.session}' not found."))
            return

    # Single prompt mode
    if args.prompt:
        try:
            result = chat.send(args.prompt, backend_name=args.backend)
            if isinstance(result, dict):
                print(result.get("content", ""))
            else:
                # Stream generator
                for chunk in result:
                    print(chunk, end="", flush=True)
                print()
        except Exception as e:
            print(formatter.error(f"Error: {e}"))
        return

    # Interactive mode
    print(formatter.bold(f"\n  NovaPilot v{__version__}"))
    print(f"  Type /help for commands, /quit to exit.\n")

    while True:
        try:
            prompt = input(f"{Colors.CYAN}> {Colors.RESET}")
            text = prompt.strip()

            if not text:
                continue

            # Handle commands
            if text == "/quit" or text == "/exit":
                break
            elif text == "/clear":
                chat.new_session()
                print(formatter.info("Session cleared."))
                continue
            elif text == "/new":
                chat.new_session()
                print(formatter.info("New session started."))
                continue
            elif text == "/help":
                print("  /quit   - Exit")
                print("  /clear  - Clear chat")
                print("  /new    - New session")
                print("  /stats  - Show stats")
                print("  /help   - Show this help")
                continue
            elif text == "/stats":
                stats = chat.get_stats()
                print(formatter.render_key_value(stats))
                continue
            elif text.startswith("/"):
                print(formatter.warning(f"Unknown command: {text}"))
                continue

            # Send message with streaming
            print(f"{Colors.BOLD}{Colors.CYAN}You:{Colors.RESET} {text}")

            try:
                for chunk in chat.send(text, stream=True, backend_name=args.backend):
                    print(chunk, end="", flush=True)
                print()
            except KeyboardInterrupt:
                print("\n" + formatter.warning("Interrupted."))
            except Exception as e:
                print(formatter.error(f"Error: {e}"))

        except (KeyboardInterrupt, EOFError):
            print()
            break

    print(formatter.dim("\nGoodbye!"))


def cmd_dashboard(args, config, formatter, logger):
    """Handle dashboard subcommand.

    Args:
        args: Parsed arguments.
        config: ConfigManager instance.
        formatter: Formatter instance.
        logger: Logger instance.
    """
    from novapilot.llm.router import LLMRouter
    from novapilot.chat.engine import ChatEngine
    from novapilot.tui.dashboard import Dashboard

    # Initialize components
    router = LLMRouter(config)
    chat = ChatEngine(llm_router=router, config_manager=config)

    # Dashboard config
    dash_config = config.get_tui_config()
    if args.theme:
        dash_config["theme"] = args.theme

    # Launch dashboard
    dashboard = Dashboard(chat_engine=chat, config=dash_config)
    dashboard.run()


def main(argv=None):
    """Main entry point for NovaPilot CLI.

    Args:
        argv: Command-line arguments (defaults to sys.argv).
    """
    parser = create_parser()
    args = parser.parse_args(argv)

    # Initialize formatter
    color_enabled = not args.no_color
    formatter = Formatter(color_enabled=color_enabled)

    # Initialize logger
    log_level = "DEBUG" if args.verbose else "INFO"
    logger = get_logger(level=log_level, color_enabled=color_enabled)

    # Initialize config
    config = ConfigManager(config_path=args.config)

    # Handle no command
    if not args.command:
        parser.print_help()
        return 0

    # Dispatch to command handler
    try:
        if args.command == "chat":
            cmd_chat(args, config, formatter, logger)
        elif args.command == "config":
            cmd_config(args, config, formatter, logger)
        elif args.command == "memory":
            cmd_memory(args, config, formatter, logger)
        elif args.command == "tools":
            cmd_tools(args, config, formatter, logger)
        elif args.command == "dashboard":
            cmd_dashboard(args, config, formatter, logger)
        else:
            parser.print_help()
            return 1

    except KeyboardInterrupt:
        print()
        return 130
    except Exception as e:
        logger.error(str(e), source="cli")
        if args.verbose:
            import traceback
            traceback.print_exc()
        else:
            print(formatter.error(f"Error: {e}"))
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
