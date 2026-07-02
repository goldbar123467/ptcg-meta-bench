from __future__ import annotations

import dataclasses
import sys
import traceback
from datetime import datetime, timezone
from enum import IntEnum
from pathlib import Path
from typing import Any

from .agent_contract import (
    CandidateAgent,
    ContractViolation,
    candidate_runtime_context,
    load_candidate_agent,
    validate_agent_selection,
    validate_initial_deck,
)


class MatchError(RuntimeError):
    def __init__(self, exception: dict[str, Any], *, engine_error: bool = False) -> None:
        super().__init__(exception["message"])
        self.exception = exception
        self.engine_error = engine_error


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _start_data_dict(start_data: Any) -> dict[str, Any]:
    return {
        "errorPlayer": getattr(start_data, "errorPlayer", None),
        "errorType": getattr(start_data, "errorType", None),
        "battlePtr": getattr(start_data, "battlePtr", None),
    }


def _exception_dict(
    exc: BaseException,
    *,
    stage: str,
    candidate_index: int | None = None,
    candidate_path: str | None = None,
    include_traceback: bool = True,
) -> dict[str, Any]:
    data: dict[str, Any] = {
        "stage": stage,
        "type": exc.__class__.__name__,
        "message": str(exc),
    }
    if candidate_index is not None:
        data["candidate_index"] = candidate_index
    if candidate_path is not None:
        data["candidate_path"] = candidate_path
    if isinstance(exc, ModuleNotFoundError):
        data["module"] = exc.name
    if isinstance(exc, ContractViolation):
        data["code"] = exc.code
        data["details"] = exc.details
    if include_traceback:
        data["traceback"] = traceback.format_exception(type(exc), exc, exc.__traceback__)
    return data


def _base_result(
    agent_a: str | Path,
    agent_b: str | Path,
    *,
    match_id: str | None,
    max_decisions: int,
    forced_first_player: int | None,
) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "match_id": match_id,
        "created_at": _utc_now(),
        "agent_a": {"path": str(Path(agent_a).resolve())},
        "agent_b": {"path": str(Path(agent_b).resolve())},
        "max_decisions": max_decisions,
        "first_player_forced": forced_first_player,
        "first_player_decision_forced": False,
        "first_player_observed": None,
        "status": "not_started",
        "winner": None,
        "draw": False,
        "decisions": 0,
        "start_data": None,
        "engine_error": False,
        "exception": None,
        "finish_exception": None,
    }


def _load_official_cg(wrapper_dir: Path) -> tuple[Any, Any]:
    wrapper = wrapper_dir.resolve()
    wrapper_text = str(wrapper)
    if wrapper_text not in sys.path:
        sys.path.insert(0, wrapper_text)

    for module_name in list(sys.modules):
        if module_name == "cg" or module_name.startswith("cg."):
            module = sys.modules[module_name]
            module_file = getattr(module, "__file__", None)
            if module_file is None:
                sys.modules.pop(module_name, None)
                continue
            try:
                Path(module_file).resolve().relative_to(wrapper)
            except ValueError:
                sys.modules.pop(module_name, None)

    import cg.sim  # noqa: F401
    import cg.api as cg_api
    import cg.game as cg_game

    for module in (cg_api, cg_game):
        module_file = getattr(module, "__file__", None)
        if module_file is None:
            raise ContractViolation(
                "official_wrapper_import_mismatch",
                "official cg module has no file path",
                module=getattr(module, "__name__", None),
            )
        try:
            Path(module_file).resolve().relative_to(wrapper)
        except ValueError as exc:
            raise ContractViolation(
                "official_wrapper_import_mismatch",
                "battle control must import cg from the official wrapper",
                module=getattr(module, "__name__", None),
                module_file=str(module_file),
                wrapper_dir=str(wrapper),
            ) from exc
    return cg_game, cg_api


def _load_candidate(path: str | Path, *, index: int, wrapper_dir: Path) -> CandidateAgent:
    try:
        return load_candidate_agent(
            path,
            official_wrapper_dir=wrapper_dir,
            module_prefix=f"candidate_{index}",
        )
    except Exception as exc:
        raise MatchError(
            _exception_dict(
                exc,
                stage="agent_import",
                candidate_index=index,
                candidate_path=str(Path(path).resolve()),
            )
        ) from exc


def _call_initial_agent(candidate: CandidateAgent, index: int, wrapper_dir: Path) -> list[int]:
    initial_obs = {"select": None, "logs": [], "current": None}
    try:
        with candidate_runtime_context(candidate.paths.root, wrapper_dir):
            result = candidate.agent(initial_obs)
        return validate_initial_deck(result, expected_deck=candidate.deck)
    except Exception as exc:
        raise MatchError(
            _exception_dict(
                exc,
                stage="initial_deck_validation",
                candidate_index=index,
                candidate_path=str(candidate.paths.root),
            )
        ) from exc


def _call_decision_agent(
    candidate: CandidateAgent,
    index: int,
    obs_dict: dict[str, Any],
    obs: Any,
    wrapper_dir: Path,
) -> list[int]:
    try:
        with candidate_runtime_context(candidate.paths.root, wrapper_dir):
            result = candidate.agent(obs_dict)
    except Exception as exc:
        raise MatchError(
            _exception_dict(
                exc,
                stage="agent_call",
                candidate_index=index,
                candidate_path=str(candidate.paths.root),
            )
        ) from exc

    try:
        return validate_agent_selection(result, obs)
    except Exception as exc:
        raise MatchError(
            _exception_dict(
                exc,
                stage="selection_validation",
                candidate_index=index,
                candidate_path=str(candidate.paths.root),
            )
        ) from exc


def _is_terminal(obs: Any) -> bool:
    current = getattr(obs, "current", None)
    return bool(current is not None and getattr(current, "result", -1) != -1)


def _winner(obs: Any) -> int | None:
    current = getattr(obs, "current", None)
    if current is None:
        return None
    result = getattr(current, "result", -1)
    return None if result == -1 else int(result)


def _simple_value(value: Any, *, depth: int = 0) -> Any:
    if depth > 5:
        return repr(value)
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, IntEnum):
        return int(value)
    if dataclasses.is_dataclass(value):
        return {
            field.name: _simple_value(getattr(value, field.name), depth=depth + 1)
            for field in dataclasses.fields(value)
        }
    if isinstance(value, dict):
        return {str(key): _simple_value(item, depth=depth + 1) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_simple_value(item, depth=depth + 1) for item in value]
    return repr(value)


def _forced_first_player_selection(obs: Any, forced_first_player: int | None) -> list[int] | None:
    if forced_first_player is None:
        return None
    select = getattr(obs, "select", None)
    current = getattr(obs, "current", None)
    if select is None or current is None:
        return None
    context = getattr(select, "context", None)
    if context is None or int(context) != 41:
        return None
    your_index = getattr(current, "yourIndex", None)
    if your_index not in (0, 1):
        raise ContractViolation(
            "invalid_first_player_prompt",
            "IS_FIRST prompt has invalid obs.current.yourIndex",
            yourIndex=your_index,
        )
    desired_option_type = 1 if your_index == forced_first_player else 2
    for option_index, option in enumerate(getattr(select, "option", []) or []):
        option_type = getattr(option, "type", None)
        if option_type is not None and int(option_type) == desired_option_type:
            return [option_index]
    raise ContractViolation(
        "missing_first_player_option",
        "IS_FIRST prompt did not expose the expected YES/NO option",
        forced_first_player=forced_first_player,
        yourIndex=your_index,
        desired_option_type=desired_option_type,
    )


def run_match(
    agent_a: str | Path,
    agent_b: str | Path,
    *,
    wrapper_dir: str | Path,
    match_id: str | None = None,
    max_decisions: int = 1000,
    forced_first_player: int | None = None,
) -> dict[str, Any]:
    if forced_first_player not in (None, 0, 1):
        raise ValueError("forced_first_player must be 0, 1, or None")

    wrapper = Path(wrapper_dir).resolve()
    result = _base_result(
        agent_a,
        agent_b,
        match_id=match_id,
        max_decisions=max_decisions,
        forced_first_player=forced_first_player,
    )
    battle_started = False
    cg_game = None

    try:
        if max_decisions < 1:
            raise MatchError(
                {
                    "stage": "argument_validation",
                    "type": "ValueError",
                    "message": "--max-decisions must be at least 1",
                }
            )

        try:
            cg_game, cg_api = _load_official_cg(wrapper)
        except Exception as exc:
            raise MatchError(_exception_dict(exc, stage="engine_import"), engine_error=True) from exc

        candidate_a = _load_candidate(agent_a, index=0, wrapper_dir=wrapper)
        candidate_b = _load_candidate(agent_b, index=1, wrapper_dir=wrapper)
        candidates = [candidate_a, candidate_b]
        result["agent_a"] = candidate_a.summary()
        result["agent_b"] = candidate_b.summary()

        _call_initial_agent(candidate_a, 0, wrapper)
        _call_initial_agent(candidate_b, 1, wrapper)

        try:
            obs_dict, start_data = cg_game.battle_start(candidate_a.deck, candidate_b.deck)
        except Exception as exc:
            raise MatchError(_exception_dict(exc, stage="battle_start"), engine_error=True) from exc

        result["start_data"] = _start_data_dict(start_data)
        battle_started = bool(result["start_data"].get("battlePtr"))
        if obs_dict is None:
            raise MatchError(
                {
                    "stage": "battle_start",
                    "type": "EngineStartError",
                    "message": "cg.game.battle_start returned obs is None",
                    "start_data": result["start_data"],
                },
                engine_error=True,
            )
        if result["start_data"].get("errorType") not in (None, 0):
            raise MatchError(
                {
                    "stage": "battle_start",
                    "type": "EngineStartError",
                    "message": "cg.game.battle_start returned nonzero errorType",
                    "start_data": result["start_data"],
                },
                engine_error=True,
            )

        while True:
            try:
                obs = cg_api.to_observation_class(obs_dict)
            except Exception as exc:
                raise MatchError(_exception_dict(exc, stage="observation_conversion"), engine_error=True) from exc

            if _is_terminal(obs):
                winner = _winner(obs)
                result["status"] = "completed"
                result["winner"] = winner
                result["draw"] = winner not in (0, 1)
                break

            current = getattr(obs, "current", None)
            if current is not None:
                first_player = getattr(current, "firstPlayer", -1)
                if first_player in (0, 1):
                    result["first_player_observed"] = int(first_player)

            if result["decisions"] >= max_decisions:
                result["status"] = "max_decisions"
                result["winner"] = None
                break

            if current is None:
                raise MatchError(
                    {
                        "stage": "observation_validation",
                        "type": "InvalidObservation",
                        "message": "nonterminal observation has current=None",
                    },
                    engine_error=True,
                )
            player_index = getattr(current, "yourIndex", None)
            if player_index not in (0, 1):
                raise MatchError(
                    {
                        "stage": "observation_validation",
                        "type": "InvalidObservation",
                        "message": "obs.current.yourIndex must be 0 or 1",
                        "yourIndex": player_index,
                    },
                    engine_error=True,
                )

            forced_selection = _forced_first_player_selection(obs, forced_first_player)
            if forced_selection is not None:
                try:
                    selection = validate_agent_selection(forced_selection, obs)
                except Exception as exc:
                    raise MatchError(_exception_dict(exc, stage="forced_first_player_validation")) from exc
                result["first_player_decision_forced"] = True
            else:
                selection = _call_decision_agent(candidates[player_index], player_index, obs_dict, obs, wrapper)

            try:
                obs_dict = cg_game.battle_select(selection)
            except Exception as exc:
                raise MatchError(_exception_dict(exc, stage="battle_select"), engine_error=True) from exc
            result["decisions"] += 1

    except MatchError as exc:
        result["status"] = "error"
        result["exception"] = exc.exception
        result["engine_error"] = exc.engine_error
    except Exception as exc:
        result["status"] = "error"
        result["exception"] = _exception_dict(exc, stage="unexpected")
    finally:
        if battle_started and cg_game is not None:
            try:
                cg_game.battle_finish()
            except Exception as exc:
                result["finish_exception"] = _exception_dict(exc, stage="battle_finish")
                result["engine_error"] = True
    return result
