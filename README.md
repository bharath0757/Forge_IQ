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
| **6. 252-Column Delivery** | Navigate to **Delivery Center** | Run `✓ Validate 252-Col Schema` and download the verified 252-column delivery CSV format with 50 attribute triplets (`ATTRIBUTE_LABEL 1..50`, `ATTRIBUTE_VALUE 1..50`, `ATTRIBUTE_UOM 1..50`). |
| **7. Operational Benchmark** | Navigate to **Benchmark** tab | Review the transparent **Operational Dataset Analysis (1,000 rows)** demonstrating real 95.9% manufacturer resolution, 79.6% brand resolution, and 100% schema compliance. |

---

## 🏛️ System Architecture

```
ForgeIQ Architecture
├── Frontend (Next.js 16 / TypeScript / Vanilla CSS Design System)
│   ├── Catalog Dashboard with Real-Time KPIs & Multi-Faceted Filters
│   ├── Authoritative Product Twin Dashboard & 6 Deterministic Description Views
│   ├── Slide-over Grounded Evidence & Verification Chain Drawer
│   ├── Multi-Source Human Review & Conflict Resolution Modal
│   ├── 8-Stage Real-Time Pipeline Processing Stream
│   ├── 252-Column Delivery Center with Interactive Schema Validation
│   └── Operational Benchmark & Evaluation Suite (1,000 rows)
│
└── Backend (FastAPI / SQLAlchemy / Python 3.9+)
    ├── Ingestion Engine (PyMuPDF parser, chunking, sanitization)
    ├── Vector Retrieval Layer (Embeddings & Cosine Similarity Store)
    ├── AI Extraction Provider (Deterministic Regex Extractor + Grounded Extraction)
    ├── Taxonomy Engine (Deterministic industrial classification rules)
    ├── Attribute Normalization Service (Unit, Range, & Dimensional Schema)
    ├── Description Engine (6 deterministic commercial descriptions without placeholders)
    ├── Deterministic Validation Engine (Range, Cross-Source Corroboration)
    ├── Confidence Scoring Engine (Multi-Signal Deterministic Multiplier)
    ├── Conflict Detection Engine (Discrepancy Grouping & Severity Matrix)
    ├── Delivery Exporter (Strict 252-column CSV mapping conforming to UniHack schema)
    └── Human Review & Audit Trail Repository (Preserved Decisions & Exports)
```

---

## 🚀 Quickstart & Local Setup

### Prerequisites
- **Python**: 3.9+ installed
- **Node.js**: 18+ or 20+ installed

---

### Local Development Setup

#### 1. Backend Setup (Terminal 1)
```bash
# Navigate to backend directory
cd backend

# Install dependencies
pip install -r requirements.txt

# Start FastAPI backend server (Runs on http://localhost:8000)
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

#### 2. Frontend Setup (Terminal 2)
```bash
# From the project root
npm install

# Start Next.js development server (Runs on http://localhost:3000)
npm run dev
```

Open **`http://localhost:3000`** in your browser.

---

## 🧪 Testing & Quality Verification

### Run Complete Backend Pytest Suite
```bash
cd backend
python -m pytest -q
```
*Result: 100 passing tests covering unit, normalization, taxonomy, extraction, conflict detection, golden path E2E, and 252-column delivery export.*

### Run Frontend Linting & Production Build
```bash
npm run lint
npm run build
```
*Result: ESLint clean (0 errors, 0 warnings) and Next.js 16 production build compiles cleanly.*

### Run 1,000-Row Operational Evaluation Run
```bash
python backend/app/evaluation/quality_runner.py
```
*Processes all 1,000 real catalog rows, calculates quality metrics in `data/quality_metrics.json`, and outputs `data/evaluated_delivery.csv` with 252 valid columns.*

---

## 📊 Operational Dataset Analysis (1,000 Rows)

| Metric | Result | Notes |
| :--- | :--- | :--- |
| **Processed Products** | 1,000 / 1,000 (100%) | 0 pipeline failures |
| **Manufacturer Resolution** | 959 / 1,000 (95.9%) | 41 remaining items lacked manufacturer in raw input (`-`) |
| **Brand Resolution** | 796 / 1,000 (79.6%) | Canonical resolution across 90+ industrial brand masters |
| **Identity Resolution** | 771 / 1,000 (77.1%) | MPN + Brand + Manufacturer composite resolution |
| **Taxonomy Resolution** | 750 / 1,000 (75.0%) | 3-tier taxonomy (`Department > Class > Fine Class`) |
| **Description Validity** | 999 / 1,000 (99.9%) | 0 occurrences of placeholder text (`None`, `Unknown`, `Unclassified`) |
| **Schema Compliance** | 252 / 252 (100%) | Exact column ordering and header match with UniHack Delivery Format |

> **Notice Regarding Official Benchmarks:**
> The competition 200-item ground truth workbook was unavailable in the workspace. Per strict anti-hallucination policies, official benchmark accuracy is explicitly reported as `UNAVAILABLE` rather than estimated or fabricated.

---

## ⚙️ Environment Variables Reference

| Variable | Default | Description |
| :--- | :--- | :--- |
| `DATABASE_URL` | `sqlite:///./test.db` | SQLAlchemy DB connection string. |
| `CORS_ORIGINS` | `http://localhost:3000,*` | Allowed CORS origin endpoints. |
| `AI_PROVIDER` | `deterministic` | Provider mode: `deterministic`, `openai`, `anthropic`. |
| `STORAGE_DIR` | `uploads` | Directory for uploaded datasheets and documents. |
| `MAX_FILE_SIZE_MB` | `50` | Maximum allowed file upload size. |

---

## 📄 License & Audit Notice
*ForgeIQ is designed for mission-critical industrial manufacturing and supply chain environments. All synthetic demo citations are generated strictly for evaluation purposes under the `DEMO DATA` label.*
