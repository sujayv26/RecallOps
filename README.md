# RecallOps — AI-Assisted Incident Response Agent

> **Hackathon MVP** — An incident response assistant that learns from your team's past incidents using persistent memory (Hindsight) and LLM reasoning (Groq).

## 🎯 What It Does

RecallOps helps engineers investigate incidents faster by:

1. **Submit** — Describe the incident and paste logs
2. **Recall** — Searches team memory for similar past incidents
3. **Analyze** — AI reasons over current incident + historical context
4. **Recommend** — Shows likely cause, steps, confidence, and evidence
5. **Verify** — Human confirms or corrects the actual resolution
6. **Learn** — Verified fix is saved to memory for next time

**Key Differentiator**: Persistent operational memory via Hindsight. Not a generic chatbot — it remembers, explains relevance, and learns from verified outcomes.

## 🏗️ Architecture

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│  Streamlit  │────▶│   FastAPI   │────▶│    Groq     │
│  Frontend   │     │   Backend   │     │   (LLM)     │
└─────────────┘     └──────┬──────┘     └─────────────┘
                           │
                    ┌──────▼──────┐
                    │  Hindsight  │
                    │  (Memory)   │
                    └─────────────┘
```

- **Frontend**: Streamlit (Python)
- **Backend**: FastAPI + Uvicorn
- **LLM**: Groq (OpenAI GPT-OSS-120B or Qwen-32B)
- **Memory**: Hindsight (Cloud or OSS)
- **Optional**: SQLite for local audit trail

## 🚀 Quick Start

### Prerequisites

- Python 3.11+
- Docker & Docker Compose (recommended)
- Groq API key: https://console.groq.com/
- Hindsight account: https://hindsight.ai/

### 1. Clone & Configure

```bash
git clone <repo-url>
cd RecallOps

# Copy environment template
cp .env.example .env

# Edit .env with your credentials
# REQUIRED: GROQ_API_KEY, HINDSIGHT_API_KEY, HINDSIGHT_BANK_ID
```

### 2. Run with Docker Compose (Recommended)

```bash
# Build and start both services
docker-compose up --build

# Backend:  http://localhost:8000
# Frontend: http://localhost:8501
# API Docs: http://localhost:8000/docs
```

### 3. Run Locally (Development)

```bash
# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# Install dependencies
pip install -e ".[backend,frontend,dev]"

# Start backend (terminal 1)
uvicorn backend.main:app --reload --port 8000

# Start frontend (terminal 2)
streamlit run frontend/app.py --server.port 8501
```

### 4. Seed Demo Memory (Optional)

```bash
# Populate Hindsight with synthetic incidents for demo
python scripts/seed_memory.py
```

## 📖 Usage

### Analyze an Incident

1. Open http://localhost:8501
2. Go to **Analyze Incident**
3. Enter:
   - **Service Name**: e.g., "Backend API"
   - **Error Description**: What happened?
   - **Log Excerpt** (optional): Paste relevant logs
4. Click **Analyze Incident**
5. Review:
   - 🔴 **Severity** & Confidence
   - 🎯 **Likely Root Cause** (Amber = AI Hypothesis)
   - 📚 **Historical Matches** (Teal = Team Memory)
   - 🛠️ **Recommended Actions**

### Confirm Resolution

After investigating and fixing:

1. Scroll to **Confirm Resolution**
2. Enter **Verified Root Cause** and **Verified Resolution**
3. Click **Save Verified Resolution**
4. The system stores this in Hindsight for future incidents

### Explore Memory

- **Memory Explorer**: Browse all verified incidents
- **Insights**: See recurring patterns/themes

## 🧪 Demo Script

For hackathon presentation:

```
1. SHOW PROBLEM
   "Engineers waste time re-investigating known issues..."

2. SUBMIT INCIDENT
   Service: "Backend API"
   Error: "HTTP 500 on /api/users, connection pool exhausted"
   Logs: [paste sample log]

3. SHOW ANALYSIS
   - Severity: High (87% confidence)
   - Root Cause: "Connection pool exhausted" ← AMBER (hypothesis)
   - Historical Match: INC-001 (92% similarity) ← TEAL (memory)
   - Memory Influence: "Historical match directly informs..."

4. CONFIRM RESOLUTION
   Root Cause: "Connection leak in UserService.getUserProfile()"
   Resolution: "Fixed leak, increased pool, deployed v2.3.1"
   → Stored as VERIFIED (violet)

5. SHOW LEARNING
   Submit related incident → Shows new memory being recalled
```

## 📁 Project Structure

```
RecallOps/
├── backend/                 # FastAPI Backend
│   ├── main.py              # API routes & app setup
│   ├── config.py            # Settings from .env
│   ├── models.py            # Pydantic schemas (API contract)
│   ├── agent.py             # Groq LLM integration
│   ├── memory.py            # Hindsight integration
│   ├── database.py          # Optional SQLite audit
│   └── requirements.txt
├── frontend/                # Streamlit Frontend
│   ├── app.py               # Main UI
│   ├── api_client.py        # Backend API client
│   └── requirements.txt
├── data/
│   └── sample_incidents.py  # Synthetic seed data (INC-001..005)
├── scripts/
│   └── seed_memory.py       # Load seed data into Hindsight
├── tests/
│   ├── test_agent.py
│   ├── test_api.py
│   └── test_memory.py
├── Dockerfile.backend
├── Dockerfile.frontend
├── docker-compose.yml
├── .env.example
├── .gitignore
├── pyproject.toml
└── README.md
```

## 🔑 Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `GROQ_API_KEY` | Yes | Groq API key |
| `GROQ_MODEL` | No | Model name (default: openai/gpt-oss-120b) |
| `HINDSIGHT_API_KEY` | Yes | Hindsight API key |
| `HINDSIGHT_BASE_URL` | No | Hindsight endpoint |
| `HINDSIGHT_BANK_ID` | Yes | Memory bank ID |
| `BACKEND_URL` | No | Backend URL (default: http://localhost:8000) |
| `FRONTEND_URL` | No | Frontend URL for CORS |
| `DATABASE_URL` | No | SQLite path for audit |

## 🧪 Testing

```bash
# Run all tests
pytest

# Run specific test modules
pytest tests/test_agent.py -v
pytest tests/test_api.py -v
pytest tests/test_memory.py -v
```

## 📝 API Reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Service health check |
| POST | `/analyze` | Analyze incident with memory recall |
| POST | `/resolve` | Store verified resolution |
| GET | `/memories` | List retained memories |
| GET | `/insights` | Get recurring patterns |
| GET | `/demo/analysis/{id}` | Get analysis by ID |
| GET | `/demo/resolution/{id}` | Get resolution by ID |

## ⚠️ Safety & Limitations

- **Advisory Only**: Never executes production commands
- **Human-in-the-Loop**: Only verified resolutions stored
- **No Autonomous Actions**: Recommends; human decides
- **Demo Data**: Synthetic incidents (INC-001..005) are fake
- **Secrets**: Never commit `.env` or expose keys in UI/logs

## 🤝 Team Responsibilities (Per PRD)

| Role | Owner |
|------|-------|
| Backend/API | Member 1 |
| Hindsight/Memory | Member 2 |
| LLM/Agent | Member 3 |
| UI/Delivery | Member 4 |

## 📄 License

Hackathon project — internal use only.