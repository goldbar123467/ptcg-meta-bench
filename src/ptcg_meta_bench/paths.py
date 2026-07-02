from __future__ import annotations

from pathlib import Path


PACKAGE_DIR = Path(__file__).resolve().parent
REPO_ROOT = PACKAGE_DIR.parents[1]

DEFAULT_SDK_ZIP = REPO_ROOT / "data" / "competition" / "pokemon-tcg-ai-battle.zip"
DEFAULT_ENGINE_CACHE = REPO_ROOT / ".ptcg_engine" / "extracted"
DEFAULT_WRAPPER_DIR = DEFAULT_ENGINE_CACHE / "sample_submission" / "sample_submission"
DECK_REGISTRY = REPO_ROOT / "decks" / "meta" / "registry.json"
SIMPLE_BASELINE_AGENT = REPO_ROOT / "examples" / "agents" / "simple_baseline"
RUNS_DIR = REPO_ROOT / "runs"
