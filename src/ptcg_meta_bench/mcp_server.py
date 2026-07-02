from __future__ import annotations

import json
import sys
from typing import Any, Callable

from . import __version__
from .cli import _benchmark_payload, decks_payload, play_payload
from .paths import SIMPLE_BASELINE_AGENT


ToolHandler = Callable[[dict[str, Any]], dict[str, Any]]


def _tool_list_decks(_arguments: dict[str, Any]) -> dict[str, Any]:
    return decks_payload()


def _tool_run_benchmark(arguments: dict[str, Any]) -> dict[str, Any]:
    games = int(arguments.get("games", 2))
    agent = arguments.get("agent") or SIMPLE_BASELINE_AGENT
    return _benchmark_payload(
        games=games,
        agent=agent,
        sdk_zip=None,
        sdk_dir=None,
        label="mcp_benchmark",
    )


def _tool_play_game(arguments: dict[str, Any]) -> dict[str, Any]:
    deck = str(arguments.get("deck") or "01_archaludon_duraludon")
    agent = arguments.get("agent") or SIMPLE_BASELINE_AGENT
    return play_payload(deck=deck, agent=agent)


def _tool_get_last_results(_arguments: dict[str, Any]) -> dict[str, Any]:
    import csv

    from .paths import RUNS_DIR

    files = sorted(RUNS_DIR.glob("*/summary.csv"))
    if not files:
        return {"status": "ok", "path": None, "rows": []}
    with files[-1].open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    return {"status": "ok", "path": str(files[-1]), "rows": rows}


TOOLS: dict[str, tuple[str, dict[str, Any], ToolHandler]] = {
    "list_decks": ("List the 10 weighted meta decks.", {"type": "object", "properties": {}}, _tool_list_decks),
    "run_benchmark": (
        "Run the local meta benchmark and return JSON results.",
        {"type": "object", "properties": {"games": {"type": "integer", "minimum": 1, "default": 2}, "agent": {"type": "string"}}},
        _tool_run_benchmark,
    ),
    "play_game": (
        "Play one readable game against a named meta deck.",
        {"type": "object", "properties": {"deck": {"type": "string"}, "agent": {"type": "string"}}},
        _tool_play_game,
    ),
    "get_last_results": ("Return the most recent meta benchmark result artifact.", {"type": "object", "properties": {}}, _tool_get_last_results),
}


def _read_message() -> dict[str, Any] | None:
    headers: dict[str, str] = {}
    while True:
        line = sys.stdin.buffer.readline()
        if line == b"":
            return None
        if line in (b"\r\n", b"\n"):
            break
        key, value = line.decode("ascii").split(":", 1)
        headers[key.lower()] = value.strip()
    return json.loads(sys.stdin.buffer.read(int(headers["content-length"])).decode("utf-8"))


def _write_message(message: dict[str, Any]) -> None:
    body = json.dumps(message, separators=(",", ":")).encode("utf-8")
    sys.stdout.buffer.write(f"Content-Length: {len(body)}\r\n\r\n".encode("ascii"))
    sys.stdout.buffer.write(body)
    sys.stdout.buffer.flush()


def _tool_specs() -> list[dict[str, Any]]:
    return [
        {"name": name, "description": description, "inputSchema": schema}
        for name, (description, schema, _handler) in TOOLS.items()
    ]


def _content(payload: dict[str, Any]) -> dict[str, Any]:
    return {"content": [{"type": "text", "text": json.dumps(payload, indent=2, sort_keys=True)}]}


def _handle(message: dict[str, Any]) -> dict[str, Any] | None:
    method = message.get("method")
    message_id = message.get("id")
    try:
        if method == "notifications/initialized":
            return None
        if method == "initialize":
            result = {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "ptcg-meta-bench", "version": __version__},
            }
        elif method == "tools/list":
            result = {"tools": _tool_specs()}
        elif method == "tools/call":
            params = message.get("params") or {}
            name = params.get("name")
            arguments = params.get("arguments") or {}
            if name not in TOOLS:
                raise RuntimeError(f"Unknown tool: {name}")
            result = _content(TOOLS[name][2](arguments))
        else:
            return {
                "jsonrpc": "2.0",
                "id": message_id,
                "error": {"code": -32601, "message": f"Unknown method: {method}"},
            }
        return {"jsonrpc": "2.0", "id": message_id, "result": result}
    except Exception as exc:
        return {"jsonrpc": "2.0", "id": message_id, "error": {"code": -32000, "message": str(exc)}}


def serve() -> int:
    while True:
        message = _read_message()
        if message is None:
            return 0
        response = _handle(message)
        if response is not None:
            _write_message(response)
