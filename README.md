# BeninSpeechLab

Open-source research prototype for **consent-aware Fon speech data collection and preparation**.

## MVP v0.1
- PCM WAV upload through FastAPI or CLI
- Format, duration and size validation
- Explicit consent, pseudonymous speaker IDs and per-recording metadata
- SHA-256 duplicate detection, private local storage and SQLite
- Review-gated JSONL manifest export
- Tests and GitHub Actions CI

**Not production-ready:** no authentication, reviewer workflow, consent withdrawal or public dataset release controls yet. Do not deploy the API publicly or commit participant audio.

## Quickstart

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
pytest -q
beninspeechlab init
uvicorn beninspeechlab.api:app --reload
```

Open http://127.0.0.1:8000/docs.

```bash
beninspeechlab ingest --file sample.wav --speaker-id speaker-001 --consent --transcript "Example"
beninspeechlab export --output exports/manifest.jsonl
```

Exports remain empty until human approval (reviewer workflow planned).

See [architecture](docs/ARCHITECTURE.md). Planned research: diversity-, uncertainty- and annotation-cost-aware audio selection, compared against random baselines using WER/CER and cost metrics. Inspired by Bonaventure Dossou's work; these algorithms are **not implemented in v0.1**.

MIT license applies to code **only**, not audio or datasets.
