from __future__ import annotations

import csv
import json
import shutil
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .agent_contract import hash_file, load_deck_csv
from .engine import resolve_wrapper_dir
from .match import run_match
from .paths import DECK_REGISTRY, RUNS_DIR, SIMPLE_BASELINE_AGENT


META_WEIGHTS = {
    "01": 15.5,
    "02": 14.6,
    "03": 11.5,
    "04": 8.3,
    "05": 7.2,
    "06": 5.9,
    "07": 5.1,
    "08": 5.0,
    "09": 4.9,
    "10": 3.8,
}


@dataclass(frozen=True)
class MetaDeck:
    deck_id: str
    name: str
    archetype: str
    path: Path
    weight: float


def _timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")


def _load_registry(path: Path = DECK_REGISTRY) -> list[MetaDeck]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    decks: list[MetaDeck] = []
    for entry in payload.get("decks", []):
        deck_id = entry["id"]
        prefix = deck_id.split("_", 1)[0]
        deck_path = path.parents[1] / Path(entry["path"]).relative_to("decks")
        decks.append(
            MetaDeck(
                deck_id=deck_id,
                name=entry["name"],
                archetype=entry["archetype"],
                path=deck_path.resolve(),
                weight=META_WEIGHTS[prefix],
            )
        )
    if len(decks) != 10:
        raise ValueError(f"registry must contain 10 meta decks, found {len(decks)}")
    return decks


def load_meta_decks() -> list[MetaDeck]:
    return _load_registry()


def _copy_candidate(temp_root: Path, *, deck: MetaDeck, pilot_agent: Path) -> Path:
    candidate_dir = temp_root / deck.deck_id
    candidate_dir.mkdir(parents=True)
    shutil.copy2(pilot_agent / "main.py", candidate_dir / "main.py")
    shutil.copy2(deck.path, candidate_dir / "deck.csv")
    (candidate_dir / "metadata.json").write_text(
        json.dumps(
            {
                "candidate_name": deck.deck_id,
                "source_type": "registered_meta_deck_opponent",
                "source_deck": str(deck.path),
                "display_name": deck.name,
                "archetype": deck.archetype,
                "meta_weight": deck.weight,
                "pilot_agent": str(pilot_agent),
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return candidate_dir


def _row_from_records(deck: MetaDeck, records: list[dict[str, Any]]) -> dict[str, Any]:
    games = len(records)
    completed = sum(1 for record in records if record.get("status") == "completed")
    wins = sum(1 for record in records if record.get("status") == "completed" and record.get("winner") == 0)
    losses = sum(1 for record in records if record.get("status") == "completed" and record.get("winner") == 1)
    draws = sum(
        1
        for record in records
        if record.get("status") == "completed" and record.get("winner") not in (0, 1)
    )
    errors = sum(1 for record in records if record.get("status") == "error")
    max_decisions = sum(1 for record in records if record.get("status") == "max_decisions")
    engine_errors = sum(1 for record in records if record.get("engine_error"))
    first_agent = sum(1 for record in records if record.get("first_player_observed") == 0)
    first_opponent = sum(1 for record in records if record.get("first_player_observed") == 1)
    decisions = [int(record.get("decisions") or 0) for record in records]
    return {
        "id": deck.deck_id,
        "weight": deck.weight,
        "games": games,
        "agent_first": first_agent,
        "opponent_first": first_opponent,
        "completed": completed,
        "wins": wins,
        "losses": losses,
        "draws": draws,
        "errors": errors,
        "max_decisions": max_decisions,
        "engine_errors": engine_errors,
        "mean_decisions": sum(decisions) / len(decisions) if decisions else 0.0,
        "win_rate": wins / games if games else 0.0,
    }


def weighted_win_rate(rows: list[dict[str, Any]]) -> float:
    weight_sum = sum(float(row["weight"]) for row in rows)
    if not weight_sum:
        return 0.0
    return sum(float(row["weight"]) * float(row["win_rate"]) for row in rows) / weight_sum


def format_results_table(rows: list[dict[str, Any]]) -> str:
    lines = [
        "id\tweight\tgames\tagent_first\topp_first\tcompleted\twins\tlosses\tdraws\terrors\tmax_decisions\tengine_errors\tmean_decisions\twin_rate"
    ]
    for row in rows:
        lines.append(
            f"{row['id']}\t{row['weight']:.1f}\t{row['games']}\t"
            f"{row['agent_first']}\t{row['opponent_first']}\t{row['completed']}\t"
            f"{row['wins']}\t{row['losses']}\t{row['draws']}\t{row['errors']}\t"
            f"{row['max_decisions']}\t{row['engine_errors']}\t"
            f"{row['mean_decisions']:.1f}\t{row['win_rate']:.3f}"
        )
    weight_sum = sum(float(row["weight"]) for row in rows)
    lines.append(f"META_WEIGHTED_OVERALL\tweight_sum={weight_sum:.1f}\twin_rate={weighted_win_rate(rows):.3f}")
    return "\n".join(lines)


def _write_outputs(out_dir: Path, rows: list[dict[str, Any]], records: list[dict[str, Any]], agent: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    with (out_dir / "matches.jsonl").open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, sort_keys=True) + "\n")

    fieldnames = [
        "id",
        "weight",
        "games",
        "agent_first",
        "opponent_first",
        "completed",
        "wins",
        "losses",
        "draws",
        "errors",
        "max_decisions",
        "engine_errors",
        "mean_decisions",
        "win_rate",
    ]
    with (out_dir / "summary.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    (out_dir / "summary.md").write_text(
        "# Meta Benchmark Summary\n\n"
        f"- Agent: `{agent}`\n"
        f"- Agent main SHA-256: `{hash_file(agent / 'main.py')}`\n"
        f"- Meta-weighted win rate: `{weighted_win_rate(rows):.3f}`\n\n"
        "```text\n"
        f"{format_results_table(rows)}\n"
        "```\n",
        encoding="utf-8",
    )


def run_meta_benchmark(
    *,
    agent: str | Path = SIMPLE_BASELINE_AGENT,
    sdk_dir: str | Path | None = None,
    sdk_zip: str | Path | None = None,
    matches: int = 1,
    max_decisions: int = 1000,
    label: str = "quickstart",
    out_dir: str | Path | None = None,
    forced_first_player: int | None = 0,
    deck_limit: int | None = None,
) -> tuple[list[dict[str, Any]], Path]:
    if matches < 1:
        raise ValueError("--matches must be at least 1")

    wrapper = resolve_wrapper_dir(sdk_dir=sdk_dir, sdk_zip=sdk_zip)
    agent_path = Path(agent).expanduser().resolve()
    load_deck_csv(agent_path / "deck.csv")
    decks = load_meta_decks()
    if deck_limit is not None:
        if deck_limit < 1:
            raise ValueError("deck_limit must be at least 1")
        decks = decks[:deck_limit]
    output = Path(out_dir).expanduser().resolve() if out_dir else RUNS_DIR / f"{_timestamp()}-{label}"

    records: list[dict[str, Any]] = []
    rows: list[dict[str, Any]] = []
    with tempfile.TemporaryDirectory(prefix="ptcg_meta_bench_") as temp_dir:
        temp_root = Path(temp_dir)
        for deck in decks:
            opponent = _copy_candidate(temp_root, deck=deck, pilot_agent=agent_path)
            deck_records: list[dict[str, Any]] = []
            for index in range(matches):
                record = run_match(
                    agent_path,
                    opponent,
                    wrapper_dir=wrapper,
                    match_id=f"{deck.deck_id}_{index + 1}",
                    max_decisions=max_decisions,
                    forced_first_player=forced_first_player,
                )
                deck_records.append(record)
                records.append(record)
            rows.append(_row_from_records(deck, deck_records))

    _write_outputs(output, rows, records, agent_path)
    failures = [
        row
        for row in rows
        if row["errors"] or row["engine_errors"] or row["max_decisions"] or row["completed"] != row["games"]
    ]
    if failures:
        raise RuntimeError(f"{len(failures)} deck benchmarks had failures; see {output}")
    return rows, output
