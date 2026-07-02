#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]


def encode(message: dict[str, Any]) -> bytes:
    body = json.dumps(message).encode("utf-8")
    return b"Content-Length: " + str(len(body)).encode("ascii") + b"\r\n\r\n" + body


def read_message(stream: Any) -> dict[str, Any]:
    headers: dict[str, str] = {}
    while True:
        line = stream.readline()
        if line in (b"\r\n", b"\n", b""):
            break
        key, value = line.decode("ascii").split(":", 1)
        headers[key.lower()] = value.strip()
    return json.loads(stream.read(int(headers["content-length"])).decode("utf-8"))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--games", type=int, default=2)
    args = parser.parse_args(argv)

    proc = subprocess.Popen(
        [sys.executable, "-m", "ptcg_meta_bench", "mcp"],
        cwd=ROOT,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    assert proc.stdin is not None
    assert proc.stdout is not None
    requests = [
        {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
        {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}},
        {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {"name": "run_benchmark", "arguments": {"games": args.games}},
        },
    ]
    transcript = []
    try:
        for request in requests:
            proc.stdin.write(encode(request))
            proc.stdin.flush()
            transcript.append({"request": request, "response": read_message(proc.stdout)})
    finally:
        proc.stdin.close()
        proc.terminate()
        proc.wait(timeout=10)
    print(json.dumps(transcript, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
