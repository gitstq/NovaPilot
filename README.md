# NovaPilot

Lightweight Terminal AI Personal Super Intelligence Engine.

Zero external dependencies. Privacy-first. Multi-LLM backend support.

## Features

- Multi-LLM backend support (OpenAI, Anthropic Claude, Ollama)
- Interactive terminal chat with streaming output
- Built-in tools: code analysis, file management, web search, calculator
- Local memory engine with TF-IDF semantic search
- TUI dashboard powered by curses
- Zero external dependencies - pure Python standard library

## Quick Start

```bash
pip install -e .
novapilot config add openai --api-key YOUR_KEY
novapilot chat
```

## License

MIT
