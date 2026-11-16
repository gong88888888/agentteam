# Minimal API Project Template

This is a scaffold copied by `start_project.py --template minimal-api`. It is
not a finished product: roles must replace the TODOs with requirement-specific
content, and code gates only accept signed tool evidence.

Included:

- `src/backend/app.py`: stdlib HTTP service + CSV rendering helper.
- `tests/test_app.py`: runnable unit tests.
- `contracts/openapi.yaml`: OpenAPI 3.1 contract used by the contract check.
- `docs/product/product-baseline.md`, `docs/architecture/architecture.md`: scaffolds.
- `tools/semgrep.yml`: local SAST rules (no network required).
