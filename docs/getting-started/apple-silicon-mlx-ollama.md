# Apple Silicon MLX + Ollama Setup

This profile is tuned for a 24GB Apple Silicon Mac Mini. It uses MLX as the
primary OpenAI-compatible local server and keeps Ollama configured as a fallback.

## Install the local profile

```bash
scripts/setup-mac-mini-24gb.sh --write-user-config
```

The script installs the development, server, and MLX extras with `uv`, copies the
Mac Mini config preset to `~/.openjarvis/config.toml`, and installs three local
agent templates:

- `local-codebase-maintainer`
- `personal-intel-router`
- `local-research-scout`

## Start MLX

```bash
uv run python -m mlx_lm server \
  --model mlx-community/Qwen2.5-7B-Instruct-4bit \
  --host 127.0.0.1 \
  --port 8080
```

Verify that port 8080 is the MLX OpenAI-compatible server:

```bash
curl -s http://127.0.0.1:8080/v1/models
```

## Optional Ollama fallback

```bash
ollama pull qwen3.5:9b
```

The preset keeps Ollama at `http://localhost:11434`, so a running Ollama daemon
can be used by switching `[engine].default` to `ollama` or by passing the engine
explicitly where supported.

For the browser UI, start the API server before the Vite frontend:

```bash
uv run jarvis serve --host 127.0.0.1 --port 8000 --engine ollama --model qwen3.5:9b
```

If the Vite terminal shows proxy `ECONNREFUSED` for `/v1/...` paths, the API
server is not running on port 8000.

## Verify

```bash
uv run jarvis doctor
uv run pytest tests/templates/test_agent_templates.py tests/core/test_preset_configs.py
```
