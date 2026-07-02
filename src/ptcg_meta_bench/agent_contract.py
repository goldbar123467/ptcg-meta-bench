from __future__ import annotations

import contextlib
import csv
import hashlib
import importlib.util
import json
import os
import re
import sys
import uuid
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
from typing import Any, Iterator


DECK_SIZE = 60


class ContractViolation(ValueError):
    """Raised when a local candidate violates the Kaggle agent contract."""

    def __init__(self, code: str, message: str, **details: Any) -> None:
        super().__init__(message)
        self.code = code
        self.details = details

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": self.__class__.__name__,
            "code": self.code,
            "message": str(self),
            "details": self.details,
        }


@dataclass(frozen=True)
class CandidatePaths:
    root: Path
    main_py: Path
    deck_csv: Path
    metadata_json: Path


@dataclass(frozen=True)
class CandidateHashes:
    main_sha256: str
    deck_sha256: str
    metadata_sha256: str


@dataclass
class CandidateAgent:
    paths: CandidatePaths
    hashes: CandidateHashes
    module_name: str
    module: ModuleType
    agent: Any
    deck: list[int]

    def summary(self) -> dict[str, Any]:
        return {
            "path": str(self.paths.root),
            "main_py": str(self.paths.main_py),
            "deck_csv": str(self.paths.deck_csv),
            "metadata_json": str(self.paths.metadata_json),
            "hashes": {
                "main_sha256": self.hashes.main_sha256,
                "deck_sha256": self.hashes.deck_sha256,
                "metadata_sha256": self.hashes.metadata_sha256,
            },
            "module_name": self.module_name,
        }


def _field(obj: Any, name: str, default: Any = None) -> Any:
    return obj.get(name, default) if isinstance(obj, dict) else getattr(obj, name, default)


def _is_plain_int(value: Any) -> bool:
    return type(value) is int


def hash_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_deck_csv(path: str | Path) -> list[int]:
    resolved = Path(path)
    if not resolved.is_file():
        raise ContractViolation("missing_deck_csv", "deck.csv does not exist", path=str(resolved))

    deck: list[int] = []
    with resolved.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.reader(handle)
        for row_number, row in enumerate(reader, start=1):
            if not row or all(cell.strip() == "" for cell in row):
                continue
            for column_number, cell in enumerate(row, start=1):
                value = cell.strip()
                if value == "":
                    continue
                try:
                    deck.append(int(value))
                except ValueError as exc:
                    raise ContractViolation(
                        "invalid_deck_card_id",
                        "deck.csv contains a non-integer card ID",
                        path=str(resolved),
                        row=row_number,
                        column=column_number,
                        value=value,
                    ) from exc

    if len(deck) != DECK_SIZE:
        raise ContractViolation(
            "invalid_deck_length",
            "deck.csv must contain exactly 60 integer card IDs",
            path=str(resolved),
            actual=len(deck),
            expected=DECK_SIZE,
        )
    return deck


def validate_candidate_dir(candidate_dir: str | Path) -> CandidatePaths:
    root = Path(candidate_dir).expanduser().resolve()
    if not root.is_dir():
        raise ContractViolation("missing_candidate_dir", "candidate directory does not exist", path=str(root))

    paths = CandidatePaths(
        root=root,
        main_py=root / "main.py",
        deck_csv=root / "deck.csv",
        metadata_json=root / "metadata.json",
    )
    missing = [
        str(path)
        for path in (paths.main_py, paths.deck_csv, paths.metadata_json)
        if not path.is_file()
    ]
    if missing:
        raise ContractViolation(
            "invalid_candidate_dir",
            "candidate directory must contain main.py, deck.csv, and metadata.json",
            path=str(root),
            missing=missing,
        )
    return paths


def candidate_hashes(paths: CandidatePaths) -> CandidateHashes:
    return CandidateHashes(
        main_sha256=hash_file(paths.main_py),
        deck_sha256=hash_file(paths.deck_csv),
        metadata_sha256=hash_file(paths.metadata_json),
    )


def _module_path_is_under(module: ModuleType, root: Path) -> bool:
    module_file = getattr(module, "__file__", None)
    if not module_file:
        return False
    try:
        Path(module_file).resolve().relative_to(root)
    except (OSError, ValueError):
        return False
    return True


def _restore_modules(snapshot: dict[str, ModuleType]) -> None:
    for name in set(sys.modules) - set(snapshot):
        sys.modules.pop(name, None)
    for name, module in snapshot.items():
        sys.modules[name] = module


@contextlib.contextmanager
def candidate_runtime_context(
    candidate_dir: str | Path,
    official_wrapper_dir: str | Path | None = None,
) -> Iterator[None]:
    root_path = Path(candidate_dir).resolve()
    wrapper_path = Path(official_wrapper_dir).resolve() if official_wrapper_dir else None
    old_cwd = os.getcwd()
    old_sys_path = list(sys.path)
    old_modules = dict(sys.modules)

    if wrapper_path:
        sys.path[:0] = [str(wrapper_path), str(root_path)]
    else:
        sys.path.insert(0, str(root_path))

    for name, module in list(sys.modules.items()):
        is_cg_module = name == "cg" or name.startswith("cg.")
        if _module_path_is_under(module, root_path):
            sys.modules.pop(name, None)
        elif is_cg_module and wrapper_path is not None and not _module_path_is_under(module, wrapper_path):
            sys.modules.pop(name, None)

    os.chdir(root_path)
    try:
        yield
    finally:
        official_cg_modules: dict[str, ModuleType] = {}
        if wrapper_path is not None:
            official_cg_modules = {
                name: module
                for name, module in sys.modules.items()
                if (name == "cg" or name.startswith("cg."))
                and _module_path_is_under(module, wrapper_path)
            }
        os.chdir(old_cwd)
        sys.path[:] = old_sys_path
        _restore_modules(old_modules)
        sys.modules.update(official_cg_modules)


def read_metadata(paths: CandidatePaths) -> dict[str, Any]:
    try:
        with paths.metadata_json.open("r", encoding="utf-8") as handle:
            value = json.load(handle)
    except json.JSONDecodeError as exc:
        raise ContractViolation(
            "invalid_metadata_json",
            "metadata.json must contain valid JSON",
            path=str(paths.metadata_json),
            error=str(exc),
        ) from exc
    if not isinstance(value, dict):
        raise ContractViolation(
            "invalid_metadata_type",
            "metadata.json must contain a JSON object",
            path=str(paths.metadata_json),
        )
    return value


def import_candidate_main(
    candidate_dir: str | Path,
    official_wrapper_dir: str | Path | None = None,
    module_prefix: str = "candidate",
) -> tuple[str, ModuleType, Any]:
    paths = validate_candidate_dir(candidate_dir)
    module_name = re.sub(r"\W+", "_", f"{module_prefix}_{paths.root.name}_{uuid.uuid4().hex}").strip("_")
    spec = importlib.util.spec_from_file_location(module_name, paths.main_py)
    if spec is None or spec.loader is None:
        raise ContractViolation(
            "candidate_import_spec_failed",
            "could not create an import spec for candidate main.py",
            path=str(paths.main_py),
        )

    module = importlib.util.module_from_spec(spec)
    try:
        with candidate_runtime_context(paths.root, official_wrapper_dir):
            sys.modules[module_name] = module
            spec.loader.exec_module(module)
    except Exception:
        sys.modules.pop(module_name, None)
        raise

    agent = getattr(module, "agent", None)
    if not callable(agent):
        sys.modules.pop(module_name, None)
        raise ContractViolation(
            "missing_agent_callable",
            "candidate main.py must define a callable agent(obs_dict)",
            path=str(paths.main_py),
        )
    return module_name, module, agent


def load_candidate_agent(
    candidate_dir: str | Path,
    official_wrapper_dir: str | Path | None = None,
    module_prefix: str = "candidate",
) -> CandidateAgent:
    paths = validate_candidate_dir(candidate_dir)
    deck = load_deck_csv(paths.deck_csv)
    hashes = candidate_hashes(paths)
    read_metadata(paths)
    module_name, module, agent = import_candidate_main(
        paths.root,
        official_wrapper_dir=official_wrapper_dir,
        module_prefix=module_prefix,
    )
    return CandidateAgent(paths, hashes, module_name, module, agent, deck)


def validate_initial_deck(result: Any, *, expected_deck: list[int] | None = None) -> list[int]:
    if not isinstance(result, list):
        raise ContractViolation(
            "invalid_initial_deck_type",
            "initial agent response must be a list[int] deck",
            actual_type=type(result).__name__,
        )
    if not all(_is_plain_int(value) for value in result):
        raise ContractViolation("invalid_initial_deck_card_type", "initial deck must contain only int card IDs")
    if len(result) != DECK_SIZE:
        raise ContractViolation(
            "invalid_initial_deck_length",
            "initial deck must contain exactly 60 card IDs",
            actual=len(result),
            expected=DECK_SIZE,
        )
    if expected_deck is not None and result != expected_deck:
        raise ContractViolation("initial_deck_mismatch", "initial agent deck does not match deck.csv")
    return list(result)


def validate_agent_selection(result: Any, obs: Any) -> list[int]:
    select = _field(obs, "select")
    if select is None:
        return validate_initial_deck(result)

    if not isinstance(result, list):
        raise ContractViolation(
            "invalid_selection_type",
            "agent selection must be a list[int]",
            actual_type=type(result).__name__,
        )
    if not all(_is_plain_int(value) for value in result):
        raise ContractViolation(
            "invalid_selection_index_type",
            "selection indexes must all be int values",
            selection=repr(result),
        )
    if len(set(result)) != len(result):
        raise ContractViolation("duplicate_selection_index", "selection indexes must be unique", selection=result)

    min_count = int(_field(select, "minCount"))
    max_count = int(_field(select, "maxCount"))
    option_count = len(_field(select, "option", []) or [])

    if len(result) < min_count or len(result) > max_count:
        raise ContractViolation(
            "invalid_selection_count",
            "selection count is outside obs.select minCount/maxCount",
            actual=len(result),
            minCount=min_count,
            maxCount=max_count,
        )

    out_of_range = [value for value in result if value < 0 or value >= option_count]
    if out_of_range:
        raise ContractViolation(
            "selection_index_out_of_range",
            "selection indexes must reference obs.select.option",
            option_count=option_count,
            out_of_range=out_of_range,
        )
    return list(result)
