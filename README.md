# Roll4Treasure

---

## Developer Quickstart (Milestone 0)

```bash
python -m venv .venv && source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
make precommit  # install hooks and run them once
make test       # run smoke tests
make dev        # run locally (serves on http://localhost:8001)
```

If `make dev` fails to find the app, update the module path inside the `Makefile` (current guess: `roll4treasure-main.app.main:app`).

## Contributing

- Create a branch per milestone step, e.g., `refactor/00-foundation`.
- CI must be green (lint, type, tests) before merging.
- Small, reviewable PRs please.
