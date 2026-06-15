# Data Intelligence Platform - Project Overview

## What is this Project?

The **Data Intelligence Platform** (also known as **Universal Data Connector System**) is a comprehensive, AI-powered data ingestion and analysis platform that combines:

1. **Data Connector System** - A FastAPI-based backend that ingests data from multiple sources (CSV, Excel, Google Sheets, PostgreSQL, APIs, S3) into PostgreSQL databases with Apache Airflow orchestration.

2. **AI-Powered Analytics Agent** - An intelligent analysis engine using LangGraph and LLMs (Groq/OpenRouter) to automatically analyze datasets, generate insights, create smart dashboards, and enable natural language data conversations.

3. **React Frontend** - A modern web interface for managing pipelines, viewing dashboards, and interacting with the system.

---

## Key Features

### Data Ingestion & Pipeline Management
- **Multi-source Connectors**: CSV, Excel, Google Sheets, PostgreSQL, REST APIs, S3
- **Data Sync Modes**: Full refresh, incremental loading, append, overwrite
- **Apache Airflow Integration**: Automated DAG generation for scheduled data pipelines
- **Pipeline Monitoring**: Real-time status tracking, logs, and metrics
- **Schema Evolution**: Automatic handling of changing data schemas

### AI-Powered Data Analysis
- **Automated Analysis**: Null detection, duplicates, statistics, outliers, correlations
- **LLM-Powered Chart Selection**: AI automatically selects the 4 most relevant charts
- **AI Summary Generation**: Plain English summaries of your data (150+ words)
- **Chatbot Interface**: Ask natural language questions about your data
- **Custom Chart Generation**: Type chart requests in natural language

### Dashboard & Visualization
- **Live Dashboards**: KPIs, charts, data quality metrics, 50-row data preview
- **Interactive Reports**: HTML reports with Jinja2 templating
- **Data Preview**: Paginated table views with sorting and filtering
- **Pipeline Monitoring**: View Airflow DAG runs, metrics, and execution logs

### Multi-Source Pipelines
- Combine multiple data sources into single pipelines
- Support for complex ETL workflows
- Automatic DAG generation for multi-source scenarios

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        FRONTEND (React)                          │
│              Port: 3001 (or 3000 for local dev)                  │
└────────────────────┬────────────────────────────────────────────┘
                     │ HTTP/API
┌────────────────────▼────────────────────────────────────────────┐
│                      BACKEND (FastAPI)                         │
│                     Port: 8000 (or 8001)                       │
├─────────────────────────────────────────────────────────────────┤
│  ┌─────────────┐  ┌──────────────┐  ┌─────────────────────┐    │
│  │   Main      │  │ Data         │  │ AI Agent            │    │
│  │   API       │  │ Connectors   │  │ (LangGraph + LLM)   │    │
│  │   Routes    │  │              │  │                     │    │
│  └──────┬──────┘  └──────┬───────┘  └──────────┬──────────┘    │
│         │                │                     │                │
│         └────────────────┴──────────┬──────────┘                │
│                                     │                           │
│  ┌──────────────────────────────────▼────────────────────┐     │
│  │              PostgreSQL Database                       │     │
│  │   (pipeline_runs, metrics, logs, user data tables)   │     │
│  └──────────────────────────────────────────────────────┘     │
└─────────────────────────────────────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────────────────┐
│                    APACHE AIRFLOW                              │
│              Port: 8081 (Web UI)                              │
│     - DAG Scheduler & Executor                                │
│     - Dynamic DAG generation from API                          │
└─────────────────────────────────────────────────────────────────┘
```

---

## Tech Stack

| Component | Technology |
|-----------|------------|
| **Backend** | FastAPI + Python |
| **Frontend** | React + TypeScript + Vite + Tailwind CSS |
| **Database** | PostgreSQL |
| **Orchestration** | Apache Airflow |
| **Agent Framework** | LangGraph |
| **LLM Providers** | Groq / OpenRouter / Together AI (OpenAI-compatible) |
| **Data Processing** | pandas, polars, numpy, scipy |
| **Charts** | Plotly, Recharts |
| **Visualization** | Jinja2 HTML templates |

---

## Project Structure

```
project_root/
├── backend/                    # FastAPI backend
│   ├── main.py                 # Main FastAPI application
│   ├── run.py                  # Entry point with DB initialization
│   ├── streamlit_app.py        # Alternative Streamlit interface
│   ├── requirements.txt          # Python dependencies
│   ├── init.sql                # Database initialization
│   ├── connectors/             # Data source connectors
│   │   ├── csv_connector.py
│   │   ├── excel_connector.py
│   │   ├── postgres_connector.py
│   │   ├── google_sheets_connector.py
│   │   ├── api_connector.py
│   │   └── s3_connector.py
│   ├── loaders/                # Database loaders
│   ├── utils/                  # Utility functions
│   │   ├── dag_generator.py
│   │   ├── multi_dag_generator.py
│   │   └── ingest_runner.py
│   └── agent/                  # AI Agent components
│       ├── agent_router.py
│       ├── dashboard_store.py
│       ├── graph/              # LangGraph nodes & edges
│       ├── tools/              # Analysis & chart tools
│       └── templates/          # HTML templates
├── frontend/                   # React frontend
│   ├── package.json
│   ├── vite.config.ts
│   ├── src/
│   │   ├── App.tsx
│   │   ├── pages/              # Dashboard, Pipelines, etc.
│   │   ├── components/         # Reusable UI components
│   │   └── lib/                # API client, utilities
│   └── README.md
├── Dataset/                    # Sample datasets
├── docker-compose.yml          # Full stack Docker setup
├── Dockerfile.backend          # Backend Docker image
├── Dockerfile.frontend         # Frontend Docker image
└── README.md                   # Original project README
```

---

## How to Run This Project

### Prerequisites

- **Docker & Docker Compose** (recommended for full stack)
- **Python 3.10+** (for local backend development)
- **Node.js 18+** (for local frontend development)
- **PostgreSQL** (if running without Docker)

---

### Option 1: Run with Docker Compose (Recommended)

This runs the entire stack including PostgreSQL, Backend, Frontend, and Airflow.

1. **Clone and navigate to the project:**
```bash
cd /home/spark/Spark_data_connector_system
```

2. **Create a `.env` file** in the project root:
```env
# Database Configuration
DB_HOST=postgres
DB_PORT=5432
DB_NAME=airflow
DB_USER=airflow
DB_PASSWORD=airflow

# Airflow Configuration
AIRFLOW_USER=admin
AIRFLOW_PASSWORD=admin
AIRFLOW_BASE_URL=http://localhost:8080/api/v1/dags
AIRFLOW__WEBSERVER__SECRET_KEY=your-secret-key-here

# LLM Provider (pick ONE)
# Option 1: Groq
GROQ_API_KEY=gsk_your_key_here
GROQ_MODEL=llama-3.3-70b-versatile

# Option 2: OpenRouter
# OPENROUTER_API_KEY=sk-or-your_key_here
# OPENROUTER_MODEL=meta-llama/llama-3.3-70b-instruct:free

# AWS S3 (optional)
AWS_ACCESS_KEY_ID=your_aws_key
AWS_SECRET_ACCESS_KEY=your_aws_secret
AWS_REGION=us-east-1

# Email Configuration (optional - for alerts)
EMAIL_SENDER=your_email@gmail.com
EMAIL_PASSWORD=your_app_password
EMAIL_RECEIVER=receiver_email@gmail.com
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587

# Windows paths (if on Windows)
WINDOWS_DOWNLOADS=/path/to/Downloads
WINDOWS_DOCUMENTS=/path/to/Documents
```

3. **Start all services:**
```bash
docker compose up -d
```

4. **Access the services:**
   - **Frontend**: http://localhost:3001
   - **Backend API**: http://localhost:8000
   - **Airflow UI**: http://localhost:8081 (login: admin/admin)
   - **PostgreSQL**: localhost:5433

5. **Stop all services:**
```bash
docker compose down
```

---

### Option 2: Run Backend Locally (Development Mode)

1. **Navigate to backend directory:**
```bash
cd /home/spark/Spark_data_connector_system/backend
```

2. **Create a virtual environment:**
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. **Install dependencies:**
```bash
pip install -r requirements.txt
```

4. **Create `.env` file** (see example above)

5. **Ensure PostgreSQL is running** and create the required tables:
```bash
# If using local PostgreSQL
psql -U airflow -d airflow -f init.sql
```

6. **Run the backend server:**
```bash
python run.py
```

The backend will start at **http://localhost:8000**

---

### Option 3: Run Frontend Locally

1. **Navigate to frontend directory:**
```bash
cd /home/spark/Spark_data_connector_system/frontend
```

2. **Install dependencies:**
```bash
npm install
```

3. **Create `.env` file:**
```env
VITE_API_BASE_URL=http://localhost:8000
```

4. **Start development server:**
```bash
npm run dev
```

The frontend will start at **http://localhost:3000**

---

### Option 4: Run with Streamlit (Alternative UI)

```bash
cd /home/spark/Spark_data_connector_system/backend
source venv/bin/activate
streamlit run streamlit_app.py
```

---

## Quick Start Guide

### 1. Ingest Data via API

```bash
# Ingest a CSV file
curl -X POST http://localhost:8000/ingest_csv \
  -H "Content-Type: application/json" \
  -d '{
    "file_path": "/path/to/your/data.csv",
    "option": "1",
    "table_name": "my_data"
  }'
```

### 2. Create a Scheduled Pipeline

```bash
curl -X POST http://localhost:8000/create_pipeline \
  -H "Content-Type: application/json" \
  -d '{
    "pipeline_name": "daily_sales",
    "connector_type": "csv",
    "table_name": "sales_data",
    "file_path": "/data/sales.csv",
    "schedule": "0 9 * * *",
    "option": "1"
  }'
```

### 3. Analyze Data with AI

```bash
# Start analysis (creates a dashboard)
curl -X POST http://localhost:8000/agent/analyze \
  -H "Content-Type: application/json" \
  -d '{
    "source_type": "postgres",
    "request": "full analysis"
  }'
```

### 4. Access the Dashboard

- Go to **http://localhost:3001** (or your frontend port)
- View pipelines, monitor runs, and explore AI-generated dashboards

---

## API Endpoints Summary

| Endpoint | Description |
|----------|-------------|
| `GET /` | Health check |
| `POST /ingest_csv` | Ingest CSV file |
| `POST /ingest_excel` | Ingest Excel file |
| `POST /ingest_postgres` | Ingest from PostgreSQL |
| `POST /ingest_google_sheet` | Ingest from Google Sheets |
| `POST /ingest_api` | Ingest from REST API |
| `POST /ingest_s3` | Ingest from S3 |
| `POST /create_pipeline` | Create scheduled pipeline (DAG) |
| `GET /pipelines` | List all pipelines |
| `DELETE /delete_pipeline/{name}` | Delete a pipeline |
| `PATCH /edit_pipeline/{name}` | Edit pipeline config |
| `GET /all_pipelines` | Get all pipeline runs |
| `GET /pipeline/{name}/runs` | Get runs for a pipeline |
| `GET /pipeline/{name}/logs` | Get pipeline logs |
| `GET /metrics/{id}` | Get pipeline metrics |
| `GET /dashboard/summary` | Get dashboard summary data |
| `GET /table/{name}` | Get table data with pagination |
| `GET /connections` | List saved connections |
| `POST /connections` | Save a connection |

---

## Configuration Options

### Sync Modes
- `full` - Complete data refresh
- `incremental` - Only fetch new/updated records based on a timestamp column

### Load Options
- `1` - Append to existing table
- `2` - Overwrite table
- `3` - Create new table (first run), then append or overwrite

---

## Troubleshooting

### Backend won't connect to database
- Check `DB_HOST` in `.env` (use `localhost` for local, `postgres` for Docker)
- Verify PostgreSQL is running: `docker compose logs postgres`

### Airflow DAGs not appearing
- Check DAG files are in `/opt/airflow/dags` (Docker)
- Verify Airflow webserver is running: `docker compose logs airflow-webserver`

### Frontend can't connect to backend
- Ensure `VITE_API_BASE_URL` is set correctly
- Check CORS settings in `main.py`

### LLM features not working
- Verify your API key is set in `.env`
- Check the selected model is available for your provider

---

## Development Tips

1. **Hot Reload**: The backend supports auto-reload during development
2. **Logs**: Check `docker compose logs -f backend` for real-time logs
3. **Database**: Connect to PostgreSQL at `localhost:5433` with credentials from `.env`
4. **Testing**: Use the Streamlit app (`streamlit_app.py`) for quick manual testing

---

## License

This project is intended for educational and development purposes.
