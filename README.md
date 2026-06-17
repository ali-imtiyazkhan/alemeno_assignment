# AI-Powered Transaction Processing Pipeline

A backend API that accepts dirty CSV transaction data, processes it asynchronously through a job queue, uses an LLM to classify transactions and flag anomalies, and generates a structured summary report.

## Tech Stack

- **API:** FastAPI
- **Database:** PostgreSQL
- **Job Queue:** Celery + Redis
- **LLM:** Gemini 1.5 Flash (free-tier)
- **Containerization:** Docker Compose

## Quick Start

### Prerequisites

- Docker & Docker Compose
- Gemini API key (optional — without it, the pipeline runs but skips LLM calls)

### Setup

1. Clone the repository:
   ```bash
   git clone <repo-url>
   cd <repo-directory>
   ```

2. (Optional) Create a `.env` file for the Gemini API key:
   ```env
   GEMINI_API_KEY=your_gemini_api_key_here
   ```

3. Start all services with a single command:
   ```bash
   docker compose up --build
   ```

   This starts: FastAPI (port 8000), Celery worker, Redis, and PostgreSQL.

4. The API is available at `http://localhost:8000`.

## API Endpoints

### 1. Upload CSV — `POST /jobs/upload`

```bash
curl -X POST http://localhost:8000/jobs/upload \
  -F "file=@transactions.csv"
```

Response:
```json
{"job_id": 1}
```

### 2. Check Job Status — `GET /jobs/{job_id}/status`

```bash
curl http://localhost:8000/jobs/1/status
```

Response (pending):
```json
{"id": 1, "status": "pending", "summary": null}
```

Response (completed):
```json
{
  "id": 1,
  "status": "completed",
  "summary": {
    "total_spend_inr": 123456.78,
    "total_spend_usd": 9876.54,
    "anomaly_count": 5,
    "risk_level": "medium"
  }
}
```

### 3. Get Full Results — `GET /jobs/{job_id}/results`

```bash
curl http://localhost:8000/jobs/1/results
```

Response:
```json
{
  "transactions": [...],
  "anomalies": [...],
  "category_spend": [
    {"category": "Food", "count": 10, "total": 25000.0},
    ...
  ],
  "narrative_summary": {
    "total_spend_inr": 123456.78,
    "total_spend_usd": 9876.54,
    "top_merchants": ["Amazon", "Flipkart", "Swiggy"],
    "anomaly_count": 5,
    "narrative": "Spending is concentrated in Shopping and Food...",
    "risk_level": "medium"
  }
}
```

### 4. List All Jobs — `GET /jobs`

```bash
curl http://localhost:8000/jobs
```

Optional filter:
```bash
curl "http://localhost:8000/jobs?status=completed"
```

## Processing Pipeline

When a job is dequeued, the worker executes:

1. **Data Cleaning** — Normalise dates, strip `$`, uppercase status/currency, fill missing categories, remove duplicates
2. **Anomaly Detection** — Flag >3× account median outliers; flag USD+domestic merchant pairs
3. **LLM Classification** — Batch-call Gemini for uncategorised transactions
4. **LLM Narrative Summary** — Single Gemini call for spend breakdown + risk assessment
5. **Retry Logic** — Up to 3 retries with exponential backoff; marks `llm_failed` on exhaustion

## Running Tests

```bash
pip install -r requirements.txt
pytest tests/ -v
```

## Project Structure

```
├── docker-compose.yml
├── Dockerfile
├── requirements.txt
├── transactions.csv          # sample data
├── .gitignore
├── README.md
├── app/
│   ├── main.py               # FastAPI entrypoint
│   ├── config.py             # settings via env vars
│   ├── database.py           # SQLAlchemy engine
│   ├── models.py             # Job, Transaction, JobSummary
│   ├── schemas.py            # Pydantic models
│   ├── api/
│   │   └── jobs.py           # API endpoints
│   └── tasks/
│       ├── worker.py         # Celery app
│       └── processing.py     # pipeline logic
└── tests/
    ├── conftest.py           # fixtures
    ├── test_cleaning.py      # unit tests for data cleaning
    ├── test_anomalies.py     # unit tests for anomaly detection
    └── test_api.py           # integration tests for API
```
