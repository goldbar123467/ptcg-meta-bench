---
name: ptcg-meta-bench
description: Use this repo to evaluate Pokemon TCG AI Battle agents locally through the ptcg CLI or MCP server.
---

# ptcg-meta-bench Agent Skill

Use CLI plus `--json` for terminal agents. Use MCP only when the host client has
MCP support.

## Required Checks

```bash
ptcg doctor --json
ptcg decks --json
```

## Output Schemas

`ptcg decks --json` returns:

```json
{
  "status": "ok",
  "deck_count": 10,
  "weight_sum": 81.8,
  "decks": [
    {
      "id": "01_archaludon_duraludon",
      "name": "Archaludon ex / Duraludon",
      "archetype": "archaludon",
      "weight": 15.5,
      "path": "decks/meta/01_archaludon_duraludon.csv"
    }
  ]
}
```

`ptcg demo --json` and `ptcg bench --json` return:

```json
{
  "status": "ok",
  "version": "1.1.0",
  "agent": "examples/agents/simple_baseline",
  "games_per_deck": 2,
  "deck_count": 10,
  "weight_sum": 81.8,
  "meta_weighted_win_rate": 1.0,
  "plain_english_summary": "Your agent beats the meta 100% weighted.",
  "run_dir": "/absolute/path/to/runs/<timestamp>-ptcg_demo",
  "rows": [
    {
      "id": "01_archaludon_duraludon",
      "weight": 15.5,
      "games": 2,
      "completed": 2,
      "wins": 2,
      "losses": 0,
      "draws": 0,
      "errors": 0,
      "engine_errors": 0,
      "max_decisions": 0,
      "win_rate": 1.0
    }
  ]
}
```

## MCP

```bash
ptcg mcp
```

Tool names:

- `list_decks`
- `run_benchmark`
- `play_game`
- `get_last_results`

Claude Desktop config:

```json
{
  "mcpServers": {
    "ptcg-meta-bench": {
      "command": "ptcg",
      "args": ["mcp"]
    }
  }
}
```
