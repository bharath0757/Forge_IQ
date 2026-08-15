# ForgeIQ — Evidence-First AI Product Intelligence Engine

> Enterprise B2B platform transforming unstructured industrial datasheets, multi-source supplier catalogs, and distributor specifications into verified, deterministic **Product Digital Twins** with grounded evidence citations, automated conflict resolution, and auditable human-in-the-loop oversight.

---

## 🎯 3-Minute Hackathon Judge Demo Walkthrough

| Step | Action | What to Observe |
| :--- | :--- | :--- |
| **1. Seed Catalog** | Click `📦 Seed 5 Demo Products` in header | Loads 5 realistic products across categories (Siemens, ABB, Schneider, Eaton, Phoenix Contact) with calculated quality scores and conflict alerts. |
| **2. Launch Pipeline** | Click `⚡ Demo Pipeline: 3RV2011` | Watch the live **8-Stage Processing Pipeline** (`01 IDENTIFY ➔ 02 DISCOVER ➔ 03 EXTRACT ➔ 04 NORMALIZE ➔ 05 VALIDATE ➔ 06 DECIDE ➔ 07 REVIEW ➔ 08 PUBLISH`) stream status logs in real time. |
| **3. Inspect Product Twin** | Navigate to **Product Twin** tab | See canonical normalized specs (`400 V`, `10 A`, `50/60 Hz`, `7.5 kW`), overall Quality Score gauge (88%), and the active conflict alert on `Current`. |
| **4. Grounded Evidence** | Click `View Evidence` on any attribute | Slide-over drawer reveals the 4-step verification chain (`SPEC ➔ EVIDENCE ➔ VALIDATION ➔ CONFIDENCE`), exact datasheet page numbers, snippet text, and mathematical score breakdown factors. |
| **5. Resolve Conflict** | Click `⚠ Review (1)` in header | Open the Human Review dialog showing the discrepancy (`10 A` in manufacturer datasheet vs `12 A` in distributor spec). Click **Select Alternative** (`10 A`) with rationale `"Verified against Siemens Datasheet p.4"`. |
| **6. Verified Status & Export** | Click `Approve & Publish Twin` then `Export JSON` | Status updates to **PUBLISHED** (Green badge), and instant download of the canonical Product Twin JSON and e-commerce CSV is generated. |

---

## 🏛️ System Architecture

```
ForgeIQ Architecture
├── Frontend (Next.js 16 / TypeScript / Vanilla CSS Design System)
│   ├── Catalog Dashboard with Real-Time KPIs & Multi-Faceted Filters
│   ├── Authoritative Product Twin Dashboard
│   ├── Slide-over Grounded Evidence & Verification Chain Drawer
│   ├── Multi-Source Human Review & Conflict Resolution Modal
│   └── 8-Stage Real-Time Pipeline Processing Stream
│
└── Backend (FastAPI / SQLAlchemy / pgvector / Python 3.9+)
    ├── Ingestion Engine (PyMuPDF parser, chunking, sanitization)
    ├── Vector Retrieval Layer (Embeddings & Cosine Similarity Store)
    ├── AI Extraction Provider (LangChain OpenAI / Deterministic Fallback)
    ├── Attribute Normalization Service (Unit, Range, & Dimensional Schema)
    ├── Deterministic Validation Engine (Range, Cross-Source Corroboration)
    ├── Confidence Scoring Engine (Multi-Signal Deterministic Multiplier)
    ├── Conflict Detection Engine (Discrepancy Grouping & Severity Matrix)
    └── Human Review & Audit Trail Repository (Preserved Decisions & Exports)
```

---

## 🚀 Quickstart & Local Setup

### Prerequisites
- **Python**: 3.9+ installed
- **Node.js**: 18+ or 20+ installed
- **Docker & Docker Compose** (optional for containerized deployment)

---

### Option A: Standalone Local Setup (Recommended for Dev & Demo)

#### 1. Backend Setup (Terminal 1)
```bash
# Navigate to backend directory
cd backend

# Create and activate virtual environment (optional)
python -m venv venv
# Windows:
venv\Scripts\activate
# Linux/macOS:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Start FastAPI backend server (Runs on http://localhost:8000)
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

#### 2. Frontend Setup (Terminal 2)
```bash
# Navigate to frontend directory
cd frontend

# Install Node dependencies
npm install

# Start Next.js development server (Runs on http://localhost:3000)
npm run dev
```

Open **`http://localhost:3000`** in your browser.

---

### Option B: Docker Compose Deployment (Production Containerized)

```bash
# Clone and enter project directory
cd Forge_IQ

# Copy environment variables
cp .env.example .env

# Build and start all services (PostgreSQL with pgvector, FastAPI, Next.js)
docker-compose up --build -d

# Check running container status
docker-compose ps

# View backend logs
docker-compose logs -f backend
```

Services will be available at:
- **Frontend App**: `http://localhost:3000`
- **Backend API Docs**: `http://localhost:8000/docs`
- **Health Check**: `http://localhost:8000/health`

---

## 🧪 Testing & Verification

### Run Complete Backend Pytest Suite
```bash
cd backend
python -m pytest -v
```
*Executes all 80 unit, integration, failure handling, and end-to-end golden path tests.*

### Run Frontend Production Build & Linting
```bash
cd frontend
npm run lint
npm run build
```

---

## ⚙️ Environment Variables Reference

| Variable | Default | Description |
| :--- | :--- | :--- |
| `DATABASE_URL` | `sqlite:///./test.db` | SQLAlchemy DB connection string (Postgres or SQLite). |
| `CORS_ORIGINS` | `http://localhost:3000,*` | Allowed CORS origin endpoints. |
| `AI_PROVIDER` | `deterministic` | Provider mode: `deterministic`, `openai`, `anthropic`. |
| `OPENAI_API_KEY` | `""` | OpenAI API key (optional; deterministic provider used if omitted). |
| `STORAGE_DIR` | `uploads` | Directory for uploaded datasheets and documents. |
| `MAX_FILE_SIZE_MB` | `50` | Maximum allowed file upload size. |
| `NEXT_PUBLIC_API_URL` | `http://localhost:8000` | Frontend backend API target URL. |

---

## 📄 License & Audit Notice
*ForgeIQ is designed for mission-critical industrial manufacturing and supply chain environments. All synthetic demo citations are generated strictly for evaluation purposes under the `DEMO DATA` label.*
