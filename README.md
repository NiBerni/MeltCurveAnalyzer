# 🧬 AI-Driven PCR Melt Curve Analyzer

![Python](https://img.shields.io/badge/Python-3.14-blue.svg?style=flat-square&logo=python&logoColor=white)
![Flask](https://img.shields.io/badge/Flask-3.1.3-green.svg?style=flat-square&logo=flask&logoColor=white)
![SQLAlchemy](https://img.shields.io/badge/SQLAlchemy-2.1.0b3-red.svg?style=flat-square)
![License](https://img.shields.io/badge/License-MIT-yellow.svg?style=flat-square)
![Build](https://img.shields.io/badge/Build-Passing-brightgreen.svg?style=flat-square)

> **⚠️ DEMO ENVIRONMENT – RESEARCH USE ONLY (RUO)**  
> *Not for diagnostic procedures. This application processes strictly anonymized data without patient identifiers (PHI)
for demonstration and evaluation purposes only.*

Welcome to the lab! 🧪 This project bridges the gap between clinical diagnostics and modern software engineering.
Standard commercial cycler software often struggles with complex multiplex melt curves, relying on rigid temperature
thresholds that fail when matrix effects or amplification biases occur.

We solve this by replacing static thresholds with a **dynamic, AI-driven data processing pipeline**. Using signal
smoothing, asymmetric baseline correction, Gaussian peak deconvolution, and unsupervised Machine Learning (clustering),
this system robustly identifies targets based on relative distances rather than absolute temperatures.

## 🏗️ Project Structure

We believe in a strict **Separation of Concerns (SoC)**. Business logic, mathematical processing, data access, and API
routing are heavily decoupled to ensure maintainability and testability.

```text
pcr_analyzer_mvp/
├── app/                      # Application Source Code
│   ├── api/                  # Routing & HTTP Delivery Layer (Flask)
│   ├── core/                 # Pure Math & ML Layer (NumPy, SciPy, Scikit-Learn)
│   ├── db/                   # Data Access Layer & Repositories (SQLAlchemy)
│   ├── ingestion/            # File Parsing & Structural Validation
│   └── services/             # Orchestration & Business Logic (The "Glue")
├── data/                     # Raw Cycler Data & Artifacts
├── docs/                     # Documentation (reST/Sphinx)
├── migrations/               # Alembic Database Migrations
└── tests/                    # 100% TDD Coverage Suite
    ├── integration/          # API & DB Integration Tests
    └── unit/                 # Isolated Component Tests
```

## 🛠️ Tech Stack & Standards

This codebase is proudly built on the bleeding edge of the Python ecosystem, rigorously adhering to **PEP 8** for style
and **PEP 20 (The Zen of Python)** for design philosophy.

* **Language:** Python >= 3.14 (fully leveraging modern type hinting: `PEP 484`, `PEP 585`, `PEP 604`).
* **Web Framework:** Flask `3.1.3` (Strictly REST API, "Smart Backend / Dumb Frontend" paradigm).
* **Database & ORM:** PostgreSQL accessed via SQLAlchemy `2.1.0b3` & psycopg `3`.
    * *Security Note:* We exclusively enforce **PEP 750 Template Strings** (`t"..."`) for any raw SQL execution to
      guarantee structural immunity against SQL injection.
* **Math & AI Engine:** NumPy `2.5.1`, Pandas `3.0.3`, SciPy `1.18.0`, Scikit-Learn `1.9.0`.
* **Authentication:** JWT via `flask-jwt-extended` with strict Role-Based Access Control (RBAC).

## 🚀 Getting Started

Follow these steps to get the environment running locally.

**1. Clone the repository and navigate into it:**

```bash
git clone https://github.com/your-username/meltcurveanalyzer.git
cd meltcurveanalyzer
```

**2. Set up a virtual environment and install dependencies:**
*(We recommend using `uv` for blazing-fast package resolution, but standard `pip` works too).*

```bash
python3.14 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

**3. Configure Environment Variables:**
Create a `.env` file in the root directory and populate it with your local development keys:

```bash
DATABASE_URL=postgresql+psycopg://pcr_admin:supersecretpassword@localhost:5432/pcr_analyzer
JWT_SECRET_KEY=super-secure-local-dev-key
```

**4. Run Database Migrations:**

```bash
alembic upgrade head
```

**5. Boot the Server:**

```bash
python main.py
# The API will be available at http://0.0.0.0:8000
```

## 💻 Usage & API Endpoints

The backend operates strictly as a REST API. Below are the core endpoints required to interact with the ingestion and
analysis pipeline.

*(💡 Tip: Check out the `MeltCurveAnalyzer_Postman_Collection.json` provided in the repository to instantly load these
requests into Postman for evaluation!)*

### 1. Authentication

* **Endpoint:** `POST /api/auth/login`
* **Description:** Authenticates the user and returns an RBAC-compliant JWT.

```bash
curl -X POST http://localhost:8000/api/auth/login \
     -H "Content-Type: application/json" \
     -d '{"username": "valid_operator", "password": "correct_password"}'
```

### 2. File Upload & Processing

* **Endpoint:** `POST /api/runs/upload`
* **Description:** Ingests a cycler CSV/XML file, runs the mathematical pipeline, and persists results. **Requires
  explicit GDPR consent payload.**

```bash
curl -X POST http://localhost:8000/api/runs/upload \
     -H "Authorization: Bearer <YOUR_JWT_TOKEN>" \
     -F "consent_gdpr_phi=true" \
     -F "template_id=COVID_MULTIPLEX_v1" \
     -F "file=@/path/to/cycler_export.xml"
```

### 3. Technical Validation (Escalation)

* **Endpoint:** `POST /api/results/<result_id>/validate`
* **Description:** RBAC-protected endpoint (requires `Senior`, `Validator`, or `Admin` role) to manually override or
  validate AI-flagged ambiguous results.

```bash
curl -X POST http://localhost:8000/api/results/123e4567-e89b-12d3-a456-426614174000/validate \
     -H "Authorization: Bearer <YOUR_JWT_TOKEN>" \
     -H "Content-Type: application/json" \
     -d '{"is_positive": false, "override_reason": "Baseline artifact confirmed."}'
```

## 🔮 Outlook (Known Issues & Future Features)

Because *code is never truly finished*, here is where the project currently stands and where it's heading:

* **Current MVP Limitations:**
    * Single-tenant architecture (assumes a single laboratory environment).
    * Color channels are evaluated in complete isolation; cross-channel Internal Control (IC) validation is not yet
      implemented.
    * No frontend UI is shipped in this repository yet (API only).
* **Planned Features:**
    * Expanded clustering algorithms (integrating DBSCAN for more adaptive noise handling).
    * LIS (Laboratory Information System) export integration via HL7/FHIR.
    * Multi-tenant organizational partitioning.

We welcome community collaboration! Feel free to open an issue or submit a pull request if you want to contribute to the
future of open-source diagnostic analysis.