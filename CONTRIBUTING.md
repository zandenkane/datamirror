# contributing

PRs welcome. If you want to add a new service parser, look at how google.py works and follow the same pattern. Each parser gets its own file in src/datamirror/parsers/.

Run tests with `pytest`. Lint with `ruff check .`.

If you find a bug in how a specific export format is parsed, open an issue with a sample of the data (redact anything personal obviously).
