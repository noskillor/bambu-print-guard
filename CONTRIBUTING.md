# Contributing

Issues and pull requests are welcome – especially reports from printers other than the P1S
(X1, A1, P1P) and tuning values that worked for you.

- **Bug reports:** include the guard log (`journalctl -u print-guard` or
  `docker compose logs guard`), your printer model and Home Assistant version.
  Remove tokens and IP addresses you don't want to share.
- **Code:** keep `print_guard.py` dependency-light (standard library + Pillow).
  Run the checks before opening a PR:

  ```bash
  pip install ruff pytest pillow
  ruff check .
  pytest
  ```
- **Never** add Obico source code or model files to this repository – see the README
  section *Credits & licenses*. Obico is licensed separately (AGPL-3.0) and is built from
  its own repository at install time; changes to Obico belong in
  [Obico's repository](https://github.com/TheSpaghettiDetective/obico-server). The CI job
  `no-third-party-code` rejects pull requests that add Obico code or model files.
