# Architecture — v0.1

Fon pilot: WAV upload (API/CLI) → validation and consent → SHA-256 deduplication → private local audio and SQLite metadata → human review (planned) → JSONL manifest export.

Modules:
- `core.py`: WAV checks, consent, ingestion, SQLite and manifests
- `api.py`: FastAPI health and upload endpoints
- `cli.py`: initialize, ingest and export
- `tests/`: consent, deduplication, invalid WAV and review-gated export
- `.github/workflows/ci.yml`: CI tests

**Limitations:** No review interface, authentication, consent withdrawal, audio normalization, VAD, ASR or active learning. The manifest currently filters by review status and transcript but does not enforce public-release licensing; never treat it as permission to publish recordings.

**Research plan:** Evaluate random vs uncertainty-, diversity- and cost-aware selection for Fon, with speaker-disjoint test sets, WER/CER and annotation-cost reporting.
