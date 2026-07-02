from __future__ import annotations

import os
import zipfile
from pathlib import Path

from .paths import DEFAULT_ENGINE_CACHE, DEFAULT_SDK_ZIP, DEFAULT_WRAPPER_DIR


REQUIRED_WRAPPER_FILES = (
    "cg/__init__.py",
    "cg/api.py",
    "cg/game.py",
    "cg/sim.py",
)

NATIVE_LIBRARY_NAMES = (
    "cg/libcg.so",
    "cg/libcg-arm64.so",
    "cg/libcg.dylib",
    "cg/cg.dll",
)


class EngineBootstrapError(RuntimeError):
    """Raised when the official Kaggle SDK wrapper cannot be found."""


def _candidate_wrapper_dirs(path: Path) -> list[Path]:
    return [
        path,
        path / "sample_submission" / "sample_submission",
        path / "sample_submission",
    ]


def normalize_wrapper_dir(path: str | Path) -> Path:
    """Accept either the wrapper directory or a parent containing it."""

    root = Path(path).expanduser().resolve()
    for candidate in _candidate_wrapper_dirs(root):
        if candidate.is_dir() and all((candidate / item).is_file() for item in REQUIRED_WRAPPER_FILES):
            return candidate
    raise EngineBootstrapError(
        "could not find official sample_submission/sample_submission wrapper under "
        f"{root}"
    )


def verify_wrapper_dir(path: str | Path) -> Path:
    wrapper = normalize_wrapper_dir(path)
    missing = [item for item in REQUIRED_WRAPPER_FILES if not (wrapper / item).is_file()]
    if missing:
        raise EngineBootstrapError(f"official wrapper is missing required files: {missing}")
    if not any((wrapper / item).is_file() for item in NATIVE_LIBRARY_NAMES):
        raise EngineBootstrapError("official wrapper is missing a native cg engine library")
    return wrapper


def extract_sdk_zip(
    sdk_zip: str | Path,
    *,
    cache_dir: str | Path = DEFAULT_ENGINE_CACHE,
    force: bool = False,
) -> Path:
    """Extract a user-downloaded Kaggle competition zip into the ignored local cache."""

    zip_path = Path(sdk_zip).expanduser().resolve()
    if not zip_path.is_file():
        raise EngineBootstrapError(f"Kaggle SDK zip not found: {zip_path}")

    cache = Path(cache_dir).expanduser().resolve()
    wrapper = cache / "sample_submission" / "sample_submission"
    if not force and wrapper.exists():
        return verify_wrapper_dir(wrapper)

    cache.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path) as archive:
        archive.extractall(cache)
    return verify_wrapper_dir(wrapper)


def resolve_wrapper_dir(
    *,
    sdk_dir: str | Path | None = None,
    sdk_zip: str | Path | None = None,
) -> Path:
    """Resolve the official wrapper from args, env, cache, or default local zip."""

    if sdk_dir:
        return verify_wrapper_dir(sdk_dir)

    env_dir = os.environ.get("PTCG_ENGINE_DIR")
    if env_dir:
        return verify_wrapper_dir(env_dir)

    if sdk_zip:
        return extract_sdk_zip(sdk_zip)

    env_zip = os.environ.get("PTCG_SDK_ZIP")
    if env_zip:
        return extract_sdk_zip(env_zip)

    if DEFAULT_WRAPPER_DIR.exists():
        return verify_wrapper_dir(DEFAULT_WRAPPER_DIR)

    if DEFAULT_SDK_ZIP.exists():
        return extract_sdk_zip(DEFAULT_SDK_ZIP)

    raise EngineBootstrapError(
        "official Kaggle SDK not found. Download pokemon-tcg-ai-battle.zip from "
        "the competition page, then pass --sdk-zip data/competition/pokemon-tcg-ai-battle.zip "
        "or set PTCG_ENGINE_DIR to an extracted sample_submission/sample_submission directory."
    )
