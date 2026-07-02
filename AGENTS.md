# AGENTS.md

Use this repo to evaluate Pokemon TCG AI Battle agents locally through the
`ptcg` CLI or MCP server.

## Required Checks

```bash
ptcg doctor --json
ptcg decks --json
```

## Champion/Challenger Recipe

Run a fast smoke benchmark first:

```bash
ptcg demo --games 2 --agent examples/agents/simple_baseline --json
```

Run a fuller comparison only after the smoke pass:

```bash
ptcg bench --games 20 --agent examples/agents/simple_baseline --json
ptcg bench --games 20 --agent path/to/challenger --json
```

Compare `meta_weighted_win_rate`, `rows[*].errors`,
`rows[*].engine_errors`, and `rows[*].max_decisions`. Treat any nonzero error
count as a failed candidate until the run artifact explains otherwise.

## MCP

Start the server:

```bash
ptcg mcp
```

Tools:

```text
list_decks
run_benchmark
play_game
get_last_results
```

Recommendation: terminal agents such as Codex should use CLI plus `--json`.
MCP-capable clients such as Claude Desktop should use `ptcg mcp` with the
client config shown in `README.md`.

## Pitfalls

- `ModuleNotFoundError: No module named 'cg'` means an import/package problem,
  not a gameplay loss.
- The Kaggle SDK zip is intentionally not committed. `ptcg doctor --json` must
  report the SDK check as `ok` before benchmark claims are valid.
- The engine has no stable seed control. Small game counts are smoke tests, not
  statistical proof.
- Nonzero `errors`, `engine_errors`, or `max_decisions` invalidate a strength
  claim until investigated.
