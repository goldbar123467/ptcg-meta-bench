# ptcg-meta-bench

[![CI](https://github.com/goldbar123467/ptcg-meta-bench/actions/workflows/ci.yml/badge.svg)](https://github.com/goldbar123467/ptcg-meta-bench/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

Local meta-weighted benchmark harness for Pokemon TCG AI Battle agents.

## What / Why

`ptcg-meta-bench` lets Kaggle Simulation competitors train and benchmark Pokemon TCG agents against a 10-deck meta panel, weighted by observed meta share. It wraps the official local engine after you provide your own Kaggle SDK download, runs full games, validates agent choices, and prints a compact matchup table.

This repo intentionally ships only a simple baseline player. It does not include tuned submission agents, private experiments, official SDK files, native engine libraries, raw Kaggle archives, or card images.

## Quickstart

Prerequisite: download `pokemon-tcg-ai-battle.zip` from the Kaggle competition page and place it at:

```text
data/competition/pokemon-tcg-ai-battle.zip
```

Install the package:

```bash
python -m pip install -e .
```

Run the mini benchmark:

```bash
python -m ptcg_meta_bench quickstart --sdk-zip data/competition/pokemon-tcg-ai-battle.zip
```

The command extracts the official SDK into the ignored `.ptcg_engine/` cache, then runs one full game against each registered meta deck.

## Sample Output

This is the sample table from `examples/meta_results_sample.csv`:

```text
id	weight	games	agent_first	opp_first	completed	wins	losses	draws	errors	max_decisions	engine_errors	mean_decisions	win_rate
01_archaludon_duraludon	15.5	1	1	0	1	1	0	0	0	0	0	160.0	1.000
02_petrel_froslass	14.6	1	1	0	1	1	0	0	0	0	0	149.0	1.000
03_energy_recycler	11.5	1	1	0	1	1	0	0	0	0	0	72.0	1.000
04_abra_alakazam	8.3	1	1	0	1	1	0	0	0	0	0	83.0	1.000
05_yveltal_risky_ruins	7.2	1	1	0	1	0	1	0	0	0	0	162.0	0.000
06_eri_wondrous_patch	5.9	1	1	0	1	1	0	0	0	0	0	160.0	1.000
07_mega_kangaskhan_ogerpon	5.1	1	1	0	1	1	0	0	0	0	0	127.0	1.000
08_mega_starmie	5.0	1	1	0	1	1	0	0	0	0	0	55.0	1.000
09_nighttime_mine_fezandipiti	4.9	1	1	0	1	1	0	0	0	0	0	125.0	1.000
10_mega_lucario	3.8	1	1	0	1	1	0	0	0	0	0	173.0	1.000
META_WEIGHTED_OVERALL	weight_sum=81.8	win_rate=0.912
```

The sample is a tiny smoke-scale run with the simple baseline and fixed first-player choice. Use larger match counts before making strength claims.

## Architecture

```text
user agent dir
  main.py / deck.csv / metadata.json
        |
        v
agent contract validator
        |
        v
official Kaggle SDK wrapper  <--- user-supplied zip or PTCG_ENGINE_DIR
        |
        v
match runner -> deck registry -> meta-weighted benchmark -> results table
```

## Plug In Your Own Agent

Create a directory with:

```text
my_agent/
  main.py
  deck.csv
  metadata.json
```

Minimal `main.py` interface:

```python
from cg.api import to_observation_class


def _read_deck() -> list[int]:
    with open("deck.csv", encoding="utf-8") as handle:
        return [int(line.strip()) for line in handle if line.strip()]


def agent(obs_dict):
    obs = to_observation_class(obs_dict)
    if obs.select is None:
        return _read_deck()
    return list(range(obs.select.minCount))
```

Pass your directory through the `--agent` option when benchmarking.

## Add Your Own Deck

Deck CSVs are one integer card ID per line, exactly 60 rows. To extend the panel:

1. Add a CSV under `decks/meta/`.
2. Add a matching entry to `decks/meta/registry.json`.
3. Assign a weight in `src/ptcg_meta_bench/benchmark.py`.
4. Re-run the quickstart benchmark and check `errors`, `engine_errors`, and `max_decisions`.

## 10-Deck Meta Panel

| ID | Archetype | Weight |
| --- | --- | ---: |
| `01_archaludon_duraludon` | Archaludon ex / Duraludon | 15.5 |
| `02_petrel_froslass` | Team Rocket's Petrel / Froslass | 14.6 |
| `03_energy_recycler` | Energy Recycler / Energy Search | 11.5 |
| `04_abra_alakazam` | Abra / Alakazam | 8.3 |
| `05_yveltal_risky_ruins` | Yveltal / Risky Ruins | 7.2 |
| `06_eri_wondrous_patch` | Eri / Wondrous Patch | 5.9 |
| `07_mega_kangaskhan_ogerpon` | Mega Kangaskhan ex / Wellspring Mask Ogerpon ex | 5.1 |
| `08_mega_starmie` | Mega Starmie ex / Ignition Energy | 5.0 |
| `09_nighttime_mine_fezandipiti` | Nighttime Mine / Fezandipiti ex | 4.9 |
| `10_mega_lucario` | Mega Lucario ex / Riolu | 3.8 |

## Notes

The official Python wrapper does not expose a public seed setter for the native engine. The smoke path forces the first-player prompt where the wrapper allows it, but native shuffling remains engine-controlled.

This is an unofficial fan project for the Kaggle Pokemon TCG AI Battle competition. It is not affiliated with, endorsed by, sponsored by, or approved by Pokemon, Nintendo, Creatures, Game Freak, or Kaggle. No card images are included.
