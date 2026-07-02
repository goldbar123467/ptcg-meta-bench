from __future__ import annotations

import os
from pathlib import Path

import pytest

from ptcg_meta_bench.benchmark import run_meta_benchmark
from ptcg_meta_bench.paths import DEFAULT_SDK_ZIP, SIMPLE_BASELINE_AGENT


def _sdk_zip() -> Path | None:
    env = os.environ.get("PTCG_SDK_ZIP")
    if env:
        return Path(env)
    if DEFAULT_SDK_ZIP.is_file():
        return DEFAULT_SDK_ZIP
    return None


def test_smoke_plays_one_full_game_with_zero_engine_errors() -> None:
    sdk_zip = _sdk_zip()
    if sdk_zip is None:
        pytest.skip("official Kaggle SDK zip is not vendored; set PTCG_SDK_ZIP to run engine smoke")

    rows, _ = run_meta_benchmark(
        agent=SIMPLE_BASELINE_AGENT,
        sdk_zip=sdk_zip,
        matches=1,
        max_decisions=1000,
        label="pytest_smoke",
        forced_first_player=0,
        deck_limit=1,
    )

    first = rows[0]
    assert first["games"] == 1
    assert first["completed"] == 1
    assert first["errors"] == 0
    assert first["engine_errors"] == 0
    assert first["max_decisions"] == 0
