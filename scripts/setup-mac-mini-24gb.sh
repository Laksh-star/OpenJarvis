#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CONFIG_SRC="$ROOT_DIR/configs/openjarvis/examples/mac-mini-24gb-mlx-ollama.toml"
CONFIG_DST="$HOME/.openjarvis/config.toml"
TEMPLATE_SRC="$ROOT_DIR/src/openjarvis/templates/data"
TEMPLATE_DST="$HOME/.openjarvis/templates/agents"
OLLAMA_BIN="${OLLAMA_BIN:-}"

WRITE_USER_CONFIG=0
PULL_OLLAMA_MODEL=0
INSTALL_DEPS=1

for arg in "$@"; do
  case "$arg" in
    --write-user-config) WRITE_USER_CONFIG=1 ;;
    --pull-ollama-model) PULL_OLLAMA_MODEL=1 ;;
    --no-deps) INSTALL_DEPS=0 ;;
    -h|--help)
      cat <<'EOF'
Usage: scripts/setup-mac-mini-24gb.sh [options]

Options:
  --write-user-config   Copy the Mac Mini profile to ~/.openjarvis/config.toml.
  --pull-ollama-model   Pull the Ollama fallback model qwen3.5:9b if ollama exists.
  --no-deps             Skip uv dependency installation.
EOF
      exit 0
      ;;
    *)
      echo "Unknown option: $arg" >&2
      exit 2
      ;;
  esac
done

if [[ "$(uname -m)" != "arm64" ]]; then
  echo "Warning: this setup profile is tuned for Apple Silicon arm64." >&2
fi

mkdir -p "$HOME/.openjarvis" "$TEMPLATE_DST"

if [[ -z "$OLLAMA_BIN" ]]; then
  if command -v ollama >/dev/null 2>&1; then
    OLLAMA_BIN="$(command -v ollama)"
  elif [[ -x /Applications/Ollama.app/Contents/Resources/ollama ]]; then
    OLLAMA_BIN="/Applications/Ollama.app/Contents/Resources/ollama"
  fi
fi

if [[ "$INSTALL_DEPS" == "1" ]]; then
  if ! command -v uv >/dev/null 2>&1; then
    echo "uv is required. Install it first: https://docs.astral.sh/uv/getting-started/installation/" >&2
    exit 1
  fi
  (cd "$ROOT_DIR" && uv sync --extra dev --extra inference-mlx --extra server)
fi

cp "$TEMPLATE_SRC/local-codebase-maintainer.toml" "$TEMPLATE_DST/"
cp "$TEMPLATE_SRC/personal-intel-router.toml" "$TEMPLATE_DST/"
cp "$TEMPLATE_SRC/local-research-scout.toml" "$TEMPLATE_DST/"

if [[ "$WRITE_USER_CONFIG" == "1" ]]; then
  if [[ -f "$CONFIG_DST" ]]; then
    backup="$CONFIG_DST.bak.$(date +%Y%m%d%H%M%S)"
    cp "$CONFIG_DST" "$backup"
    echo "Backed up existing config to $backup"
  fi
  cp "$CONFIG_SRC" "$CONFIG_DST"
  echo "Wrote $CONFIG_DST"
else
  echo "Config preset available at $CONFIG_SRC"
  echo "Run again with --write-user-config to install it."
fi

if [[ "$PULL_OLLAMA_MODEL" == "1" ]]; then
  if [[ -n "$OLLAMA_BIN" ]]; then
    "$OLLAMA_BIN" pull qwen3.5:9b
  else
    echo "ollama is not installed; skipping fallback model pull." >&2
  fi
fi

cat <<EOF

Next:
  MLX server:    uv run python -m mlx_lm server --model mlx-community/Qwen2.5-7B-Instruct-4bit --host 127.0.0.1 --port 8080
  Ollama model:  ollama pull qwen3.5:9b
  Verify:        uv run jarvis doctor
  API server:    uv run jarvis serve --host 127.0.0.1 --port 8000 --engine ollama --model qwen3.5:9b
  Try agent:     uv run jarvis ask --agent orchestrator --engine ollama --model qwen3.5:9b "Summarize this repo setup"
EOF
