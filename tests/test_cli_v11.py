from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]


def sdk_zip() -> Path | None:
    env = os.environ.get("PTCG_SDK_ZIP")
    if env and Path(env).is_file():
        return Path(env)
    local = ROOT / "data" / "competition" / "pokemon-tcg-ai-battle.zip"
    if local.is_file():
        return local
    return None


def run_ptcg(*args: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    zip_path = sdk_zip()
    if zip_path is not None:
        env["PTCG_SDK_ZIP"] = str(zip_path)
    return subprocess.run(
        ["ptcg", *args],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def test_decks_json_lists_ten_weighted_archetypes() -> None:
    result = run_ptcg("decks", "--json")

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["status"] == "ok"
    assert len(payload["decks"]) == 10
    assert payload["decks"][0]["id"] == "01_archaludon_duraludon"
    assert payload["decks"][0]["weight"] == 15.5
    assert "archetype" in payload["decks"][0]


def test_bench_json_user_error_is_friendly_without_traceback() -> None:
    result = run_ptcg("bench", "--games", "0", "--json")

    assert result.returncode != 0
    payload = json.loads(result.stdout)
    assert payload["status"] == "error"
    assert "--games must be at least 1" in payload["message"]
    assert "Traceback" not in result.stdout + result.stderr


def test_doctor_json_reports_ready_state_when_sdk_available() -> None:
    if sdk_zip() is None:
        pytest.skip("official Kaggle SDK zip is not available")

    result = run_ptcg("doctor", "--json")

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    checks = {check["name"]: check for check in payload["checks"]}
    assert payload["status"] == "ok"
    assert checks["python"]["status"] == "ok"
    assert checks["dependencies"]["status"] == "ok"
    assert checks["sdk"]["status"] == "ok"


def test_demo_json_runs_real_short_benchmark_when_sdk_available() -> None:
    if sdk_zip() is None:
        pytest.skip("official Kaggle SDK zip is not available")

    result = run_ptcg("demo", "--games", "1", "--json")

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["status"] == "ok"
    assert payload["games_per_deck"] == 1
    assert len(payload["rows"]) == 10
    assert 0.0 <= payload["meta_weighted_win_rate"] <= 1.0
    assert Path(payload["run_dir"]).is_dir()


def test_mcp_smoke_client_runs_benchmark_when_sdk_available() -> None:
    if sdk_zip() is None:
        pytest.skip("official Kaggle SDK zip is not available")

    result = subprocess.run(
        [sys.executable, "scripts/mcp_smoke_client.py", "--games", "1"],
        cwd=ROOT,
        env={**os.environ, "PTCG_SDK_ZIP": str(sdk_zip())},
        capture_output=True,
        text=True,
        check=False,
        timeout=120,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    transcript = json.loads(result.stdout)
    tool_names = {tool["name"] for tool in transcript[1]["response"]["result"]["tools"]}
    assert {"list_decks", "run_benchmark", "play_game", "get_last_results"}.issubset(tool_names)
    benchmark_payload = json.loads(transcript[2]["response"]["result"]["content"][0]["text"])
    assert benchmark_payload["status"] == "ok"
    assert benchmark_payload["games_per_deck"] == 1
