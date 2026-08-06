# Data Intelligence Platform

A FastAPI-based AI-powered data analysis platform that automatically analyzes your data, generates smart dashboards, picks the most relevant charts using an LLM, and lets you chat with your data in real time.

---

##  Features

- **Multi-source Data Ingestion** — CSV, Excel, Google Sheets, PostgreSQL, S3, API
- **Automated Analysis** — Null analysis, duplicate detection, statistics, outlier detection, correlation
- **LLM-Powered Chart Selection** — AI automatically picks the 4 most relevant charts for your dataset
- **Live Dashboard** — KPIs, charts, data quality details, and a 50-row data preview
- **AI Summary** — LLM writes a 150+ word plain English summary of your data
- **Chatbot Sidebar** — Ask natural language questions about your data
- **Custom Chart Generator** — Type any chart request; replace existing charts or add as Chart 5
- **Live Pipeline Page** — Monitor Airflow DAG runs, metrics, and logs from PostgreSQL
- **Homepage** — View and manage all session dashboards in one place

---

##  Tech Stack

| Layer | Technology |
|---|---|
| Backend | FastAPI + Python |
| Agent Framework | LangGraph |
| LLM | Groq / OpenRouter / Together AI (OpenAI-compatible) |
| Database | PostgreSQL via psycopg2 |
| Analysis | pandas, numpy, scipy |
| Charts | Plotly (base64 PNG) |
| Report | Jinja2 HTML templates |
| Frontend | Plain HTML + JS (served by FastAPI) |
| State Store | In-memory Python dict |
| Task Runner | `run.py` → uvicorn |

---

##  Project Structure

See [PROJECT_OVERVIEW.md](PROJECT_OVERVIEW.md#project-structure) for the full
tree. All Python lives under `backend/`; the dashboard agent subtree is:

```
project_root/
  .env                          ← DB credentials + LLM keys (see .env.example)
  backend/
    run.py                      ← Starts uvicorn
    main.py                     ← FastAPI app, includes agent_router
    requirements.txt
    agent/
      __init__.py
      logger.py                 ← Custom logger
      dashboard_store.py        ← In-memory dashboard state store
      agent_router.py           ← All FastAPI routes
      graph/
        state.py                ← PipelineState TypedDict
        nodes.py                ← LangGraph nodes
        edges.py                ← Conditional edges
        graph.py                ← Builds + compiles LangGraph
        onthefly.py             ← On-the-fly chart generation
      tools/
        data_tools.py           ← Data fetching from all sources
        analysis_tools.py       ← Analysis logic
        chart_tools.py          ← Plotly chart generators
        report_tools.py         ← Jinja2 HTML report + PDF export
      templates/
        home.html
        dashboard.html
        pipeline.html
        report.html
      reports/                  ← Auto-created, generated reports (gitignored)
```

---

##  Setup & Installation

### 1. Clone the Repository

```bash
git clone https://github.com/your-username/data-intelligence-platform.git
cd data-intelligence-platform
```

### 2. Create a Virtual Environment

```bash
python -m venv venv

# Windows
venv\Scripts\activate

# Mac/Linux
source venv/bin/activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure Environment Variables

Create a `.env` file in the project root:

```env
# ── LLM Provider (pick ONE) ──────────────────────────────

# Option 1: Groq 
GROQ_API_KEY=gsk_your_key_here
GROQ_MODEL=llama-3.3-70b-versatile

# Option 2: OpenRouter 
# OPENROUTER_API_KEY=sk-or-your_key_here
# OPENROUTER_MODEL=meta-llama/llama-3.3-70b-instruct:free

# ── PostgreSQL ───────────────────────────────────────────
DB_HOST=localhost
DB_PORT=5432
DB_NAME=airflow
DB_USER=airflow
DB_PASSWORD=airflow
```

### 5. Initialize the Database

Run the `init.sql` file against your PostgreSQL instance to create the required tables:

```bash
psql -U airflow -d airflow -f init.sql
```

This creates these tables:
- `pipeline_runs`
- `pipeline_logs`
- `pipeline_metrics`
- `airflow_pipeline_runs`
- `pipeline_dag_logs`

### 6. Run the Server

```bash
python run.py
```

Server starts at **http://localhost:8001**

---

##  Accessing the App

Open your browser and go to:

| Page | URL |
|---|---|
|  Homepage | `http://localhost:8001/agent/home` |
|  Dashboard | `http://localhost:8001/agent/dashboard/{id}` |
|  Live Pipeline | `http://localhost:8001/agent/dashboard/{id}/pipeline` |
|  Reports | `http://localhost:8001/agent/reports` |

> **Note:** There is no separate frontend to start. FastAPI serves all HTML pages directly — just open your browser.

---

##  How to Analyze Data

1. Go to `http://localhost:8001/agent/home`
2. Click **"+ Connect Dataset"**
3. Choose your source type (`csv`, `excel`, `postgres`, `google_sheet`, `api`)
4. Fill in the required fields (e.g. file path for CSV)
5. Click **Analyze** and wait for the pipeline to complete
6. You'll be redirected to your live dashboard

### Example API Request

```bash
curl -X POST http://localhost:8001/agent/analyze \
  -H "Content-Type: application/json" \
  -d '{
    "source_type": "csv",
    "file_path": "C:/Users/you/data.csv",
    "request": "full analysis"
  }'
```

Response:
```json
{
  "dashboard_id": "a1b2c3d4",
  "dashboard_url": "/agent/dashboard/a1b2c3d4",
  "report_url": "/agent/reports/xxxx",
  "quality_score": 85,
  "grade": "Good"
}
```

---

##  How the Agent & LLM Work

The platform uses **LangGraph** as the orchestrator. It runs each analysis node in sequence:

```
fetch_data → null_analysis → duplicate_check → stats → outliers
    → correlation → quality_score → generate_charts (LLM) → llm_summary (LLM) → build_report
```

### Where LLM is Used
| Feature | Description |
|---|---|
| Chart Selection | LLM picks the 4 most relevant charts based on your data |
| AI Summary | LLM writes a plain English summary of the analysis |
| Chatbot | LLM answers your natural language questions about the data |
| Custom Charts | LLM generates charts from natural language requests |

### Where LLM is NOT Used
| Task | Tool Used |
|---|---|
| Null analysis | pandas |
| Duplicate detection | pandas |
| Statistics (mean/std/skew) | pandas + scipy |
| Outlier detection | IQR + Z-score (numpy) |
| Correlation matrix | pandas |
| Quality score | Pure math logic |
| Chart rendering | Plotly |

---

##  Known Limitations & Roadmap

| Feature | Status |
|---|---|
| File upload endpoint (multipart) | 🔲 Planned — currently requires local file path |
| Persistent storage (SQLite) | 🔲 Planned — dashboards reset on server restart |
| Authentication / Login | 🔲 Planned |
| Export dashboard as PDF | 🔲 Planned — only reports are PDF-exportable currently |
| More chart types (box, heatmap) | 🔲 Planned |
| Dataset comparison side by side | 🔲 Planned |
| Scheduled background refresh | 🔲 Planned |
| S3 connector (full implementation) | 🔲 Planned — currently stubbed |

---

##  Contributing

Pull requests are welcome! For major changes, please open an issue first to discuss what you'd like to change.
