# Shared: ptcg-meta-bench v1.1.0

I updated the open-source local benchmark harness for Pokemon TCG AI Battle:

https://github.com/goldbar123467/ptcg-meta-bench/releases/tag/v1.1.0

One-paste install after downloading the Kaggle competition zip:

```bash
PTCG_SDK_ZIP="$HOME/Downloads/pokemon-tcg-ai-battle.zip" bash -c "$(curl -fsSL https://raw.githubusercontent.com/goldbar123467/ptcg-meta-bench/v1.1.0/install.sh)"
```

Windows PowerShell:

```powershell
$env:PTCG_SDK_ZIP="$env:USERPROFILE\Downloads\pokemon-tcg-ai-battle.zip"; irm https://raw.githubusercontent.com/goldbar123467/ptcg-meta-bench/v1.1.0/install.ps1 | iex
```

New in v1.1.0:

- `ptcg demo`, `ptcg bench`, `ptcg decks`, `ptcg play`, and `ptcg doctor`.
- JSON output for AI agents: add `--json` to the CLI commands.
- MCP server for MCP clients: `ptcg mcp`.
- CI configured to run installer, doctor, demo, and smoke checks on Linux and Windows.

Tested locally on Linux with the official Kaggle SDK zip. The CI matrix is set
up for Linux and Windows using the same installer flow.
