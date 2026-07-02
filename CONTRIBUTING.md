# Contributing

Issues and pull requests are welcome.

Please keep contributions focused on the public benchmark harness:

- Do not add Pokemon images, card scans, official SDK files, native engine libraries, raw Kaggle archives, credentials, or private submission agents.
- Keep new benchmark artifacts small. Put bulky local runs under `runs/`, which is ignored.
- Add or update tests when changing agent loading, deck validation, engine bootstrap, or benchmark scoring.
- Run `python -m pytest` before opening a pull request.

The official Kaggle SDK is intentionally not vendored. Local tests that need the native engine should point `PTCG_SDK_ZIP` or `PTCG_ENGINE_DIR` at your own downloaded copy.
