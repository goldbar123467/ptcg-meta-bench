from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path
from typing import Any

import typer
from rich.console import Console
from rich.progress import BarColumn, Progress, TextColumn, TimeElapsedColumn
from rich.table import Table

from . import __version__
from .benchmark import (
    _copy_candidate,
    format_results_table,
    load_meta_decks,
    run_meta_benchmark,
    weighted_win_rate,
)
from .engine import EngineBootstrapError, extract_sdk_zip, resolve_wrapper_dir
from .match import run_match
from .paths import DEFAULT_SDK_ZIP, SIMPLE_BASELINE_AGENT


console = Console()
app = typer.Typer(
    add_completion=False,
    help="Pokemon TCG AI Battle local benchmark tools.",
    no_args_is_help=True,
)


class UserFacingError(RuntimeError):
    def __init__(self, message: str, *, fix: str | None = None) -> None:
        super().__init__(message)
        self.fix = fix


def _json(payload: dict[str, Any]) -> None:
    typer.echo(json.dumps(payload, indent=2, sort_keys=True))


def _relative(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(Path.cwd().resolve()))
    except ValueError:
        return str(path.resolve())


def _deck_dict(deck: Any) -> dict[str, Any]:
    return {
        "id": deck.deck_id,
        "name": deck.name,
        "archetype": deck.archetype,
        "weight": deck.weight,
        "path": _relative(deck.path),
    }


def decks_payload() -> dict[str, Any]:
    decks = load_meta_decks()
    return {
        "status": "ok",
        "deck_count": len(decks),
        "weight_sum": sum(deck.weight for deck in decks),
        "decks": [_deck_dict(deck) for deck in decks],
    }


def _benchmark_payload(
    *,
    games: int,
    agent: Path,
    sdk_zip: Path | None,
    sdk_dir: Path | None,
    label: str,
    deck_limit: int | None = None,
) -> dict[str, Any]:
    if games < 1:
        raise UserFacingError("--games must be at least 1")
    try:
        rows, out_dir = run_meta_benchmark(
            agent=agent,
            sdk_zip=sdk_zip,
            sdk_dir=sdk_dir,
            matches=games,
            max_decisions=1000,
            label=label,
            forced_first_player=0,
            deck_limit=deck_limit,
        )
    except EngineBootstrapError as exc:
        raise UserFacingError(
            str(exc),
            fix="Set PTCG_SDK_ZIP to pokemon-tcg-ai-battle.zip or pass --sdk-zip PATH.",
        ) from exc
    weighted = weighted_win_rate(rows)
    return {
        "status": "ok",
        "version": __version__,
        "agent": _relative(agent),
        "games_per_deck": games,
        "deck_count": len(rows),
        "weight_sum": sum(row["weight"] for row in rows),
        "meta_weighted_win_rate": weighted,
        "plain_english_summary": f"Your agent beats the meta {weighted * 100:.0f}% weighted.",
        "run_dir": str(out_dir),
        "rows": rows,
    }


def _render_results(payload: dict[str, Any]) -> None:
    table = Table(title="Meta Benchmark Results")
    for column in ("Deck", "Weight", "Games", "Wins", "Losses", "Errors", "Win Rate"):
        table.add_column(column, justify="right" if column != "Deck" else "left")
    for row in payload["rows"]:
        table.add_row(
            row["id"],
            f"{row['weight']:.1f}",
            str(row["games"]),
            str(row["wins"]),
            str(row["losses"]),
            str(row["errors"] + row["engine_errors"] + row["max_decisions"]),
            f"{row['win_rate']:.3f}",
        )
    console.print(table)
    console.print(f"[bold green]{payload['plain_english_summary']}[/]")
    console.print(f"Run artifacts: {payload['run_dir']}")


def _handle_error(exc: Exception, *, json_output: bool) -> None:
    payload: dict[str, Any] = {"status": "error", "message": str(exc)}
    fix = getattr(exc, "fix", None)
    if fix:
        payload["fix"] = fix
    if json_output:
        _json(payload)
    else:
        console.print(f"[bold red]Error:[/] {payload['message']}")
        if fix:
            console.print(f"[yellow]Fix:[/] {fix}")
    raise typer.Exit(1)


def _sdk_options(
    sdk_zip: Path | None,
    sdk_dir: Path | None,
) -> tuple[Path | None, Path | None]:
    return sdk_zip, sdk_dir


def _run_benchmark_with_progress(
    *,
    games: int,
    agent: Path,
    sdk_zip: Path | None,
    sdk_dir: Path | None,
    label: str,
) -> dict[str, Any]:
    with Progress(
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("{task.completed}/{task.total}"),
        TimeElapsedColumn(),
        console=console,
    ) as progress:
        task = progress.add_task("Benchmarking meta decks", total=10)
        payload = _benchmark_payload(
            games=games,
            agent=agent,
            sdk_zip=sdk_zip,
            sdk_dir=sdk_dir,
            label=label,
        )
        progress.update(task, completed=10)
    return payload


def play_payload(
    *,
    deck: str,
    agent: Path,
    sdk_zip: Path | None = None,
    sdk_dir: Path | None = None,
) -> dict[str, Any]:
    wrapper = resolve_wrapper_dir(sdk_dir=sdk_dir, sdk_zip=sdk_zip)
    decks_list = load_meta_decks()
    selected = next(
        (
            item
            for item in decks_list
            if deck.lower() in {item.deck_id.lower(), item.archetype.lower(), item.name.lower()}
        ),
        None,
    )
    if selected is None:
        raise UserFacingError(f"Unknown deck: {deck}", fix="Run ptcg decks and choose one listed ID.")
    with tempfile.TemporaryDirectory(prefix="ptcg_play_") as temp_dir:
        opponent = _copy_candidate(Path(temp_dir), deck=selected, pilot_agent=agent)
        record = run_match(
            agent,
            opponent,
            wrapper_dir=wrapper,
            match_id=f"play_{selected.deck_id}",
            max_decisions=1000,
            forced_first_player=0,
        )
    return {
        "status": "ok" if record["status"] in {"completed", "max_decisions"} else "error",
        "deck": _deck_dict(selected),
        "agent": _relative(agent),
        "match": {
            key: record.get(key)
            for key in (
                "schema_version",
                "match_id",
                "created_at",
                "status",
                "winner",
                "draw",
                "decisions",
                "engine_error",
                "exception",
                "first_player_forced",
                "first_player_observed",
            )
        },
        "turn_log": [
            f"Played {record.get('decisions')} decisions against {selected.name}.",
            f"Game ended with status {record.get('status')} and winner {record.get('winner')}.",
        ],
    }


@app.command()
def demo(
    games: int = typer.Option(1, "--games", help="Games to play against each meta deck."),
    agent: Path = typer.Option(SIMPLE_BASELINE_AGENT, "--agent", help="Agent folder to benchmark."),
    sdk_zip: Path | None = typer.Option(None, "--sdk-zip", help="Path to pokemon-tcg-ai-battle.zip."),
    sdk_dir: Path | None = typer.Option(None, "--sdk-dir", help="Extracted sample_submission directory."),
    json_output: bool = typer.Option(False, "--json", help="Print machine-readable JSON."),
) -> None:
    """Run a short benchmark with friendly progress and a weighted summary."""

    try:
        sdk_zip, sdk_dir = _sdk_options(sdk_zip, sdk_dir)
        if json_output:
            _json(_benchmark_payload(games=games, agent=agent, sdk_zip=sdk_zip, sdk_dir=sdk_dir, label="ptcg_demo"))
        else:
            _render_results(
                _run_benchmark_with_progress(games=games, agent=agent, sdk_zip=sdk_zip, sdk_dir=sdk_dir, label="ptcg_demo")
            )
    except Exception as exc:
        _handle_error(exc, json_output=json_output)


@app.command()
def bench(
    games: int = typer.Option(20, "--games", help="Games to play against each meta deck."),
    agent: Path = typer.Option(SIMPLE_BASELINE_AGENT, "--agent", help="Agent folder to benchmark."),
    sdk_zip: Path | None = typer.Option(None, "--sdk-zip", help="Path to pokemon-tcg-ai-battle.zip."),
    sdk_dir: Path | None = typer.Option(None, "--sdk-dir", help="Extracted sample_submission directory."),
    json_output: bool = typer.Option(False, "--json", help="Print machine-readable JSON."),
) -> None:
    """Benchmark an agent against the full weighted 10-deck meta panel."""

    try:
        sdk_zip, sdk_dir = _sdk_options(sdk_zip, sdk_dir)
        if json_output:
            _json(_benchmark_payload(games=games, agent=agent, sdk_zip=sdk_zip, sdk_dir=sdk_dir, label="ptcg_bench"))
        else:
            _render_results(
                _run_benchmark_with_progress(games=games, agent=agent, sdk_zip=sdk_zip, sdk_dir=sdk_dir, label="ptcg_bench")
            )
    except Exception as exc:
        _handle_error(exc, json_output=json_output)


@app.command()
def decks(json_output: bool = typer.Option(False, "--json", help="Print machine-readable JSON.")) -> None:
    """List the 10 weighted meta archetypes."""

    try:
        payload = decks_payload()
        if json_output:
            _json(payload)
            return
        table = Table(title="Weighted Meta Decks")
        table.add_column("ID")
        table.add_column("Weight", justify="right")
        table.add_column("Archetype")
        table.add_column("Name")
        for deck in payload["decks"]:
            table.add_row(deck["id"], f"{deck['weight']:.1f}", deck["archetype"], deck["name"])
        console.print(table)
    except Exception as exc:
        _handle_error(exc, json_output=json_output)


@app.command()
def play(
    deck: str = typer.Option(..., "--deck", help="Deck id, archetype, or exact display name."),
    agent: Path = typer.Option(SIMPLE_BASELINE_AGENT, "--agent", help="Agent folder to use as player 0."),
    sdk_zip: Path | None = typer.Option(None, "--sdk-zip", help="Path to pokemon-tcg-ai-battle.zip."),
    sdk_dir: Path | None = typer.Option(None, "--sdk-dir", help="Extracted sample_submission directory."),
    json_output: bool = typer.Option(False, "--json", help="Print machine-readable JSON."),
) -> None:
    """Play one game against a meta deck and print a readable summary."""

    try:
        payload = play_payload(deck=deck, agent=agent, sdk_zip=sdk_zip, sdk_dir=sdk_dir)
        if json_output:
            _json(payload)
            return
        console.print(f"[bold]Agent:[/] {payload['agent']}")
        console.print(f"[bold]Opponent:[/] {payload['deck']['name']}")
        for line in payload["turn_log"]:
            console.print(line)
    except Exception as exc:
        _handle_error(exc, json_output=json_output)


@app.command()
def doctor(json_output: bool = typer.Option(False, "--json", help="Print machine-readable JSON.")) -> None:
    """Check Python, dependencies, default agent, and the Kaggle SDK path."""

    checks: list[dict[str, str]] = []
    checks.append({"name": "python", "status": "ok", "detail": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}", "fix": ""})
    for module in ("rich", "typer"):
        __import__(module)
    checks.append({"name": "dependencies", "status": "ok", "detail": "rich and typer installed", "fix": ""})
    try:
        wrapper = resolve_wrapper_dir()
        checks.append({"name": "sdk", "status": "ok", "detail": str(wrapper), "fix": ""})
    except Exception as exc:
        checks.append({
            "name": "sdk",
            "status": "error",
            "detail": str(exc),
            "fix": "Set PTCG_SDK_ZIP to pokemon-tcg-ai-battle.zip or pass --sdk-zip to benchmark commands.",
        })
    checks.append({
        "name": "default_agent",
        "status": "ok" if SIMPLE_BASELINE_AGENT.is_dir() else "error",
        "detail": str(SIMPLE_BASELINE_AGENT),
        "fix": "" if SIMPLE_BASELINE_AGENT.is_dir() else "Reinstall the package from the repo root.",
    })
    payload = {
        "status": "ok" if all(check["status"] == "ok" for check in checks) else "error",
        "version": __version__,
        "checks": checks,
    }
    if json_output:
        _json(payload)
    else:
        table = Table(title="ptcg doctor")
        table.add_column("Check")
        table.add_column("Status")
        table.add_column("Detail")
        table.add_column("Fix")
        for check in checks:
            table.add_row(check["name"], check["status"], check["detail"], check["fix"])
        console.print(table)
    if payload["status"] != "ok":
        raise typer.Exit(1)


@app.command("mcp")
def mcp_command() -> None:
    """Run the stdio MCP server."""

    from .mcp_server import serve as serve_mcp

    raise typer.Exit(serve_mcp())


@app.command("bootstrap")
def bootstrap_command(
    sdk_zip: Path = typer.Option(DEFAULT_SDK_ZIP, "--sdk-zip", help="Path to pokemon-tcg-ai-battle.zip."),
    force: bool = typer.Option(False, "--force", help="Re-extract the SDK cache."),
) -> None:
    """v1.0-compatible command: extract and verify the Kaggle SDK."""

    wrapper = extract_sdk_zip(sdk_zip, force=force)
    typer.echo(f"ENGINE_WRAPPER\t{wrapper}")


@app.command("list-decks")
def list_decks_command() -> None:
    """v1.0-compatible command: list registered meta decks."""

    typer.echo("id\tweight\tarchetype\tname")
    for item in load_meta_decks():
        typer.echo(f"{item.deck_id}\t{item.weight:.1f}\t{item.archetype}\t{item.name}")


@app.command("quickstart")
def quickstart_command(
    sdk_zip: Path | None = typer.Option(None, "--sdk-zip", help="Path to pokemon-tcg-ai-battle.zip."),
    sdk_dir: Path | None = typer.Option(None, "--sdk-dir", help="Extracted sample_submission directory."),
    agent: Path = typer.Option(SIMPLE_BASELINE_AGENT, "--agent", help="Agent folder to benchmark."),
    max_decisions: int = typer.Option(1000, "--max-decisions"),
    label: str = typer.Option("quickstart", "--label"),
) -> None:
    """v1.0-compatible command: run one game against every registered deck."""

    rows, out_dir = run_meta_benchmark(
        agent=agent,
        sdk_dir=sdk_dir,
        sdk_zip=sdk_zip,
        matches=1,
        max_decisions=max_decisions,
        label=label,
    )
    typer.echo(f"RUN_DIR\t{out_dir}")
    typer.echo(format_results_table(rows))


@app.command("benchmark")
def benchmark_command(
    sdk_zip: Path | None = typer.Option(None, "--sdk-zip", help="Path to pokemon-tcg-ai-battle.zip."),
    sdk_dir: Path | None = typer.Option(None, "--sdk-dir", help="Extracted sample_submission directory."),
    agent: Path = typer.Option(SIMPLE_BASELINE_AGENT, "--agent", help="Agent folder to benchmark."),
    matches: int = typer.Option(1, "--matches"),
    max_decisions: int = typer.Option(1000, "--max-decisions"),
    label: str = typer.Option("benchmark", "--label"),
    out_dir: Path | None = typer.Option(None, "--out-dir"),
) -> None:
    """v1.0-compatible command: run the meta benchmark."""

    rows, out_path = run_meta_benchmark(
        agent=agent,
        sdk_dir=sdk_dir,
        sdk_zip=sdk_zip,
        matches=matches,
        max_decisions=max_decisions,
        label=label,
        out_dir=out_dir,
    )
    typer.echo(f"RUN_DIR\t{out_path}")
    typer.echo(format_results_table(rows))


@app.command("smoke")
def smoke_command(
    sdk_zip: Path | None = typer.Option(None, "--sdk-zip", help="Path to pokemon-tcg-ai-battle.zip."),
    sdk_dir: Path | None = typer.Option(None, "--sdk-dir", help="Extracted sample_submission directory."),
    agent: Path = typer.Option(SIMPLE_BASELINE_AGENT, "--agent", help="Agent folder to benchmark."),
    max_decisions: int = typer.Option(1000, "--max-decisions"),
) -> None:
    """v1.0-compatible command: play one full game and assert zero engine errors."""

    rows, out_dir = run_meta_benchmark(
        agent=agent,
        sdk_dir=sdk_dir,
        sdk_zip=sdk_zip,
        matches=1,
        max_decisions=max_decisions,
        label="smoke",
        forced_first_player=0,
        deck_limit=1,
    )
    typer.echo(f"RUN_DIR\t{out_dir}")
    typer.echo(format_results_table(rows))


def main(argv: list[str] | None = None) -> int:
    try:
        app(args=argv)
    except KeyboardInterrupt:
        console.print("\nInterrupted.", file=sys.stderr)
        return 130
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
