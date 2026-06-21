# QUICKSTART — medagent-core

> **⚠️ RESEARCH USE ONLY. NOT for clinical deployment.**

Get the agent running locally in under 5 minutes.

---

## Prerequisites

- Python 3.10+
- [uv](https://github.com/astral-sh/uv) or pip
- Docker & Docker Compose (optional)
- At least one LLM API key (OpenAI, Anthropic, or Google)

---

## Option A — Local Python (Fastest)

### 1. Clone and install

```bash
git clone https://github.com/Francis1998/medagent-core.git
cd medagent-core

# With uv (recommended):
uv pip install -e ".[dev]"

# With pip:
pip install -e ".[dev]"
```

### 2. Configure

```bash
cp .env.example .env
# Edit .env — set at least one LLM API key and change PII_HASH_SALT
```

### 3. Build the sample knowledge base

```bash
python scripts/ingest_kb.py --sample
```

### 4. Start the API server

```bash
uvicorn medagent.api.main:app --host 0.0.0.0 --port 8000 --reload
```

The API is now running at http://localhost:8000. Open http://localhost:8000/docs for the interactive Swagger UI.

### 5. Send a clinical query

```bash
curl -X POST http://localhost:8000/analyze \
  -H "Content-Type: application/json" \
  -d '{
    "patient_context": {
      "patient_id_hash": "a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2",
      "age": 65,
      "sex": "male",
      "chief_complaint": "Chest pain radiating to left arm, diaphoresis",
      "clinical_notes": "Patient presents with 2-hour history of crushing substernal chest pain radiating to left arm. Associated diaphoresis and nausea. ECG shows ST elevation in V1-V4.",
      "diagnoses_history": ["Essential hypertension"],
      "medications": [
        {"name": "aspirin", "dosage": "81mg", "route": "oral"},
        {"name": "metoprolol", "dosage": "25mg", "route": "oral"}
      ],
      "lab_results": [
        {"test_name": "Troponin I", "value": "2.4", "unit": "ng/mL", "abnormal": true}
      ]
    },
    "query": "What is the differential diagnosis for this presentation?"
  }'
```

---

## Option B — Docker Compose

```bash
git clone https://github.com/Francis1998/medagent-core.git
cd medagent-core

cp .env.example .env
# Edit .env with your API keys

docker-compose up --build
```

The API will be available at http://localhost:8000 once the container health check passes (~15 seconds).

---

## Running Tests

```bash
pytest tests/ -v
```

Expected: all tests pass. Estimated runtime: ~30 seconds.

---

## Running Benchmarks

### MedQA (USMLE-style accuracy)

```bash
# Demo mode (no data file required):
python scripts/eval_medqa.py --max-samples 3

# Full run (requires data file):
python scripts/eval_medqa.py \
    --data-path data/medqa_usmle_4_options_test.jsonl \
    --max-samples 100
```

Results are saved to `results/medqa_eval.json`.

### DrugBank interaction detection

```bash
python scripts/eval_drugbank.py
```

Results are saved to `results/drugbank_eval.json`.

---

## Key Endpoints

| Endpoint | Method | Description |
|---|---|---|
| `/health` | GET | Readiness probe |
| `/analyze` | POST | Full clinical reasoning run |
| `/drug-interactions` | POST | Drug-drug interaction check |
| `/docs` | GET | Swagger UI |
| `/redoc` | GET | ReDoc API docs |

---

## Next Steps

- Read [CONFIGURATION.md](CONFIGURATION.md) for all configuration options
- Read [ARCHITECTURE.md](ARCHITECTURE.md) for system internals
- Read [SAFETY.md](SAFETY.md) for the safety policy and constraints
- Ingest your own corpus: `python scripts/ingest_kb.py --help`
