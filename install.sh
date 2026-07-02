#!/usr/bin/env bash
set -euo pipefail

say() { printf '%s\n' "$*"; }
fail() { printf 'ptcg install: %s\n' "$*" >&2; exit 1; }

if ! command -v python3 >/dev/null 2>&1; then
  fail "Python 3 is required. Install Python 3.10 or newer, then run this command again."
fi
if ! python3 - <<'PY' >/dev/null
import sys
raise SystemExit(0 if sys.version_info >= (3, 10) else 1)
PY
then
  fail "Python 3.10 or newer is required. Your python3 is too old."
fi
if ! command -v git >/dev/null 2>&1; then
  fail "git is required. Install git, then run this command again."
fi

PTCG_REPO_URL="${PTCG_REPO_URL:-https://github.com/goldbar123467/ptcg-meta-bench.git}"
PTCG_REF="${PTCG_REF:-main}"
PTCG_INSTALL_DIR="${PTCG_INSTALL_DIR:-$HOME/.local/share/ptcg-meta-bench}"
PTCG_BIN_DIR="${PTCG_BIN_DIR:-$HOME/.local/bin}"
PTCG_SOURCE_DIR="$PTCG_INSTALL_DIR/source"
PTCG_VENV_DIR="$PTCG_INSTALL_DIR/venv"

mkdir -p "$PTCG_INSTALL_DIR" "$PTCG_BIN_DIR"

if [ -d "$PTCG_SOURCE_DIR/.git" ]; then
  say "ptcg is already installed at $PTCG_INSTALL_DIR; updating it."
  git -C "$PTCG_SOURCE_DIR" fetch --all --tags --quiet
else
  say "Installing ptcg into $PTCG_INSTALL_DIR."
  git clone --quiet "$PTCG_REPO_URL" "$PTCG_SOURCE_DIR" || fail "Could not clone $PTCG_REPO_URL."
fi

git -C "$PTCG_SOURCE_DIR" checkout --quiet "$PTCG_REF" || fail "Could not check out $PTCG_REF."

say "Creating isolated Python environment."
python3 -m venv "$PTCG_VENV_DIR" || fail "Could not create a Python virtual environment."
"$PTCG_VENV_DIR/bin/python" -m pip install --upgrade pip >/dev/null
"$PTCG_VENV_DIR/bin/python" -m pip install -e "$PTCG_SOURCE_DIR" >/dev/null
ln -sf "$PTCG_VENV_DIR/bin/ptcg" "$PTCG_BIN_DIR/ptcg"

if [ -n "${PTCG_SDK_ZIP:-}" ]; then
  [ -f "$PTCG_SDK_ZIP" ] || fail "PTCG_SDK_ZIP points to a file that does not exist: $PTCG_SDK_ZIP"
  mkdir -p "$PTCG_SOURCE_DIR/data/competition"
  cp "$PTCG_SDK_ZIP" "$PTCG_SOURCE_DIR/data/competition/pokemon-tcg-ai-battle.zip"
  "$PTCG_VENV_DIR/bin/ptcg" bootstrap --sdk-zip "$PTCG_SOURCE_DIR/data/competition/pokemon-tcg-ai-battle.zip" >/dev/null
fi

say "Running ptcg doctor."
if ! "$PTCG_VENV_DIR/bin/ptcg" doctor; then
  fail "ptcg installed, but doctor found a problem. If the SDK is missing, set PTCG_SDK_ZIP to your Kaggle zip and rerun."
fi

say "Running ptcg demo."
"$PTCG_VENV_DIR/bin/ptcg" demo
say "ptcg installed. Add $PTCG_BIN_DIR to PATH if the ptcg command is not found in a new shell."
