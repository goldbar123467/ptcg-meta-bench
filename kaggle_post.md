# Shared: ptcg-meta-bench, a local meta benchmark for Pokemon TCG AI Battle

I open-sourced a small local benchmark harness for Pokemon TCG AI Battle:

https://github.com/goldbar123467/ptcg-meta-bench

What it gives you:

- Local full-game runs through the official Kaggle engine wrapper.
- A weighted 10-deck meta panel for quick sanity checks.
- A simple plug-in agent layout: `main.py`, `deck.csv`, `metadata.json`.
- Friendly CLI commands for humans plus `--json` output for terminal agents.
- An MCP server for MCP-capable clients.
- Contract checks for invalid decks, bad selections, engine errors, and max-decision stalls.

One-paste Linux install after downloading `pokemon-tcg-ai-battle.zip` from the
competition page:

```bash
PTCG_SDK_ZIP="$HOME/Downloads/pokemon-tcg-ai-battle.zip" bash -c "$(curl -fsSL https://raw.githubusercontent.com/goldbar123467/ptcg-meta-bench/v1.1.0/install.sh)"
```

Windows PowerShell:

```powershell
$env:PTCG_SDK_ZIP="$env:USERPROFILE\Downloads\pokemon-tcg-ai-battle.zip"; irm https://raw.githubusercontent.com/goldbar123467/ptcg-meta-bench/v1.1.0/install.ps1 | iex
```

Useful commands after install:

```bash
ptcg doctor
ptcg decks
ptcg demo
ptcg bench --games 20 --agent examples/agents/simple_baseline
ptcg demo --games 2 --json
ptcg mcp
```

This repo does not include the official SDK zip, native engine libraries, card
images, private submissions, or tuned leaderboard agents. You provide your own
competition zip from Kaggle; the installer copies/extracts it into an ignored
local cache.

The included `examples/agents/simple_baseline` is deliberately simple. The
point is to give everyone a reproducible local harness and a compact meta panel
for checking whether an agent can actually play full games without contract or
engine errors.
