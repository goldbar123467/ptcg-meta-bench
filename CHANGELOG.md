# Changelog

## v1.1.0 - 2026-07-02

- Added the `ptcg` Typer/Rich CLI with `demo`, `bench`, `decks`, `play`,
  `doctor`, and `mcp` commands.
- Added JSON output for CLI commands so terminal agents can parse benchmark,
  deck, doctor, and play results.
- Added Linux and Windows installers that create isolated environments and run
  `ptcg demo`.
- Added a minimal stdio MCP server exposing `list_decks`, `run_benchmark`,
  `play_game`, and `get_last_results`.
- Added README quickstarts, AGENTS/SKILL guidance, CI matrix configuration, and
  installer/CLI regression tests.

## v1.0.0

- Initial public local meta benchmark release.
