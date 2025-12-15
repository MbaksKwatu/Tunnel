# FundIQ Tunnel - Complete Application Documentation

> Comprehensive guide to the FundIQ application architecture, setup, deployment, and key files.

---

## Table of Contents

1. [Project Overview](#project-overview)
2. [Architecture](#architecture)
3. [Directory Structure](#directory-structure)
4. [Core Technologies](#core-technologies)
5. [Key Components](#key-components)
6. [Setup & Installation](#setup--installation)
7. [Deployment](#deployment)
8. [Environment Configuration](#environment-configuration)
9. [Key Files & Their Purposes](#key-files--their-purposes)
10. [API Endpoints](#api-endpoints)
11. [Database Schema](#database-schema)
12. [Frontend Pages](#frontend-pages)
13. [Troubleshooting](#troubleshooting)

---

## Project Overview

**FundIQ Tunnel** is an AI-powered financial intelligence platform designed for investment teams to process, analyze, and extract structured data from financial documents.

### Key Features
- 📄 **Multi-Format Processing**: PDF, CSV, XLSX file handling
- 🤖 **AI-Powered Extraction**: Automatic table and transaction data extraction using OpenAI
- 📊 **Data Analysis**: Anomaly detection, unsupervised learning, financial insights
- 📈 **Real-time Dashboard**: Interactive data visualization and reporting
- 💾 **Flexible Storage**: Supabase (production) or SQLite (demo)
- 🚀 **Two Deployment Modes**: Production and Demo/Local
- 🔐 **Secure Authentication**: Supabase Auth integration

---

## Architecture

### System Design

```
┌──────────────────────────────────────────────────────────────────┐
│                        CLIENT LAYER                              │
├──────────────────────────────────────────────────────────────────┤
│ Next.js 14 Frontend (React 18)                                   │
│ ├─ Pages: /, /simple-page, /dashboard, /reports, /actions       │
│ ├─ Components: FileUpload, DataReview, DocumentList, Dashboard   │
│ └─ Libraries: Supabase-JS, Axios, Recharts, Tailwind            │
└──────────────────┬───────────────────────────────────────────────┘
                   │ HTTP/REST
┌──────────────────▼───────────────────────────────────────────────┐
│                      API LAYER                                    │
├──────────────────────────────────────────────────────────────────┤
│ FastAPI Backend (Python 3.11.6)                                  │
│ ├─ File Processing:   /upload, /parse, /download               │
│ ├─ Data Management:   /documents, /extracted-rows              │
│ ├─ Analysis:          /anomalies, /insights, /evaluate         │
│ ├─ Reporting:         /reports, /dashboard                     │
│ ├─ AI Features:       /llm-actions (OpenAI integration)        │
│ └─ Database Mutations: /dashboard/mutate                        │
└──────────────────┬───────────────────────────────────────────────┘
                   │ SQL
┌──────────────────▼───────────────────────────────────────────────┐
│                    DATABASE LAYER                                 │
├──────────────────────────────────────────────────────────────────┤
│ PRIMARY: Supabase PostgreSQL (Production)                        │
│   ├─ Tables: documents, extracted_rows, anomalies, insights     │
│   ├─ RLS Policies: Service role access control                  │
│   └─ Real-time Subscriptions: Data sync                         │
│                                                                   │
│ FALLBACK: SQLite (Demo/Local Development)                       │
│   ├─ Local file: fundiq_local.db                                │
│   └─ Used by: simple_main.py for demo mode                      │
└──────────────────────────────────────────────────────────────────┘
```

### Data Flow

```
User Uploads File
      ↓
Frontend sends to /upload endpoint
      ↓
Backend receives and validates
      ↓
Parser (PDF/CSV/XLSX) extracts tables
      ↓
Data stored in database
      ↓
Anomaly Detection Engine runs
      ↓
Insights Generated (if OpenAI key available)
      ↓
Frontend polls /documents for status
      ↓
Data available for review/download
```

---

## Directory Structure

```
/Tunnel/
│
├── 📦 Frontend (Next.js)
│   ├── app/
│   │   ├── page.tsx                    # Main homepage
│   │   ├── layout.tsx                  # Root layout
│   │   ├── globals.css                 # Global styles
│   │   ├── fonts.ts                    # Font definitions
│   │   ├── simple-page.tsx             # Demo page wrapper
│   │   ├── dashboard/page.tsx          # Dashboard page
│   │   ├── reports/page.tsx            # Reports page
│   │   ├── actions/page.tsx            # Actions page
│   │   ├── evaluate/page.tsx           # Evaluation page
│   │   ├── companion/page.tsx          # AI companion page
│   │   ├── debug/page.tsx              # Debug page
│   │   ├── connect-data/page.tsx       # Data connection page
│   │   └── simple-page/
│   │       ├── page.tsx                # Demo page
│   │       └── page-component.tsx      # Demo page component
│   │
│   ├── components/
│   │   ├── FileUpload.tsx              # Main file upload component
│   │   ├── SimpleFileUpload.tsx        # Demo upload component
│   │   ├── DocumentList.tsx            # Document listing
│   │   ├── SimpleDocumentList.tsx      # Demo document listing
│   │   ├── DataReview.tsx              # Data review/table view
│   │   ├── DynamicDashboard.tsx        # Interactive dashboard
│   │   ├── AnomalyTable.tsx            # Anomaly visualization
│   │   ├── InsightList.tsx             # Insights display
│   │   ├── EvaluateView.tsx            # Evaluation interface
│   │   ├── MetricCard.tsx              # Metric card component
│   │   ├── LineChartCard.tsx           # Chart component
│   │   ├── NotesPanel.tsx              # Notes management
│   │   ├── BrandHeader.tsx             # Header component
│   │   ├── FeatureCard.tsx             # Feature card
│   │   ├── SelectInvesteeModal.tsx     # Investee selection modal
│   │   ├── InvesteeConfirmModal.tsx    # Confirmation modal
│   │   ├── SaveDashboardModal.tsx      # Dashboard save modal
│   │   ├── ShareModal.tsx              # Share functionality modal
│   │   ├── TemplateSelector.tsx        # Template selector
│   │   └── Layout/                     # Layout sub-components
│   │
│   ├── lib/
│   │   ├── supabase.ts                 # Supabase client (production)
│   │   ├── simple_supabase.ts          # Demo client (SQLite)
│   │   ├── types.ts                    # TypeScript type definitions
│   │   ├── dashboardSchema.ts          # Dashboard schema
│   │   ├── evaluate.ts                 # Evaluation utilities
│   │   ├── reportTemplates.ts          # Report templates
│   │   └── chart-utils.ts              # Chart utilities
│   │
│   ├── public/
│   │   └── fonts/                      # Font assets
│   │
│   └── styles/
│       └── globals.css                 # Global styling
│
├── 🐍 Backend (FastAPI)
│   ├── backend/
│   │   ├── main.py                     # Production backend (Supabase)
│   │   ├── simple_main.py              # Demo backend (SQLite)
│   │   │
│   │   ├── parsers.py                  # Document parsing logic
│   │   ├── anomaly_engine.py           # Anomaly detection
│   │   ├── unsupervised_engine.py      # Unsupervised learning
│   │   ├── evaluate_engine.py          # Evaluation engine
│   │   ├── insight_generator.py        # AI insight generation
│   │   ├── report_generator.py         # Report generation
│   │   ├── custom_report.py            # Custom reporting
│   │   ├── notes_manager.py            # Notes management
│   │   ├── debug_logger.py             # Debug logging
│   │   ├── local_storage.py            # Local storage interface
│   │   ├── generate_test_data.py       # Test data generation
│   │   ├── seed_demo_data.py           # Demo data seeding
│   │   │
│   │   ├── routes/
│   │   │   ├── dashboard_mutation.py   # Dashboard API endpoints
│   │   │   └── llm_actions.py          # OpenAI integration
│   │   │
│   │   ├── tests/                      # Test files
│   │   │   ├── test_api_upload.py
│   │   │   ├── test_parsers.py
│   │   │   ├── test_service_role.py
│   │   │   ├── test_supabase.py
│   │   │   └── test_unsupervised.py
│   │   │
│   │   ├── test_data/                  # Sample test files
│   │   ├── test_sample_files/          # Test documents
│   │   ├── test_output/                # Test output
│   │   ├── reports/                    # Generated reports
│   │   ├── data/                       # Data files
│   │   │
│   │   ├── requirements.txt            # Python dependencies (pinned)
│   │   ├── runtime.txt                 # Python 3.11.6 specification
│   │   ├── Procfile                    # Render deployment config
│   │   ├── render.yaml                 # Render service config
│   │   ├── railway.toml                # Railway deployment config
│   │   ├── .env                        # Environment variables
│   │   ├── .env.example                # Example env template
│   │   ├── README.md                   # Backend documentation
│   │   ├── RUN_TESTS.sh                # Test runner script
│   │   ├── venv/                       # Virtual environment
│   │   └── fundiq_local.db             # SQLite database (demo)
│   │
│   └── api/                            # Alternative API structure
│       └── (deprecated duplicate)
│
├── 🗄️ Database
│   ├── supabase/
│   │   └── migrations/                 # Database migrations
│   │
│   └── fix_supabase.sql                # RLS policy fixes
│       fix_rls_final.sql               # Additional RLS fixes
│
├── 📚 Configuration & Deployment
│   ├── next.config.js                  # Next.js configuration
│   ├── tsconfig.json                   # TypeScript configuration
│   ├── package.json                    # Node.js dependencies
│   ├── tailwind.config.ts              # Tailwind CSS config
│   ├── postcss.config.js               # PostCSS config
│   ├── .env.local                      # Local environment
│   ├── .env.production.example         # Production env template
│   ├── .env.production.template        # Alternative template
│   ├── env-template.txt                # Manual env template
│   ├── start-production.sh             # Production startup script
│   ├── start-simple.sh                 # Demo startup script
│   ├── start-standalone.js             # Standalone launcher
│   ├── prepare_deploy.sh               # Pre-deployment script
│   ├── railway.toml                    # Railway config
│   ├── .railwayignore                  # Railway ignore rules
│   ├── render.yaml                     # Render config
│   └── Dockerfile                      # Docker container config
│
├── 📖 Documentation
│   ├── README.md                       # Project overview
│   ├── START_HERE.md                   # Quick start guide
│   ├── QUICK_START.md                  # Fast setup
│   ├── SETUP.md                        # Detailed setup
│   ├── DEPLOYMENT.md                   # Deployment guide
│   ├── FILE_STRUCTURE.txt              # File structure
│   ├── IMPLEMENTATION_SUMMARY.md       # Implementation notes
│   ├── TESTING_GUIDE.md                # Testing instructions
│   ├── PROJECT_OVERVIEW.md             # Project details
│   ├── ANOMALIES_README.md             # Anomaly detection docs
│   ├── PROCESSING_CONTROLS.md          # Data controls
│   ├── BUG_FIXES.md                    # Known issues
│   └── [40+ more markdown docs]
│
├── 🎯 Test & Sample Data
│   ├── test-data/
│   │   └── sample.csv                  # Sample CSV file
│   └── Statement_All_Transactions_*.pdf # Sample PDF
│
└── 🔧 Git & Build
    ├── .git/                           # Git repository
    ├── .gitignore                      # Git ignore rules
    ├── package-lock.json               # Node dependencies lock
    └── node_modules/                   # Installed Node packages
```

---

## Core Technologies

### Frontend Stack
```
Next.js 14.1.0          - React framework with SSR/SSG
React 18.2.0            - UI library
TypeScript 5.0          - Type safety
Tailwind CSS 3.3.0      - Utility-first CSS
Recharts 2.10.3         - Data visualization
Supabase-JS 2.39.3      - Backend client
Axios 1.13.2            - HTTP client
React Dropzone 14.2.3   - File upload handling
Framer Motion 12.23.24  - Animations
Lucide React 0.312.0    - Icon library
```

### Backend Stack
```
FastAPI 0.115.0         - Modern Python web framework
Uvicorn 0.30.0          - ASGI server
Pandas 2.2.2            - Data manipulation
NumPy 1.26.4            - Numerical computing
PDFPlumber 0.10.3       - PDF parsing
OpenAI 1.44.0           - AI/LLM integration
Supabase 2.8.1          - Backend as a Service
Python-dotenv 1.0.1     - Environment config
Python-multipart 0.0.9  - Form data handling
```

### Database
```
Supabase PostgreSQL     - Production database
SQLite                  - Demo/local database
```

### Deployment
```
Render                  - Primary deployment platform
Railway                 - Alternative deployment
Docker                  - Containerization
```

---

## Key Components

### 1. **Frontend Components**

#### FileUpload.tsx
- Main file upload interface for production mode
- Accepts PDF, CSV, XLSX files
- Shows upload progress and status
- Integrates with Supabase storage

#### SimpleFileUpload.tsx
- Demo mode upload component
- Uses local storage/SQLite
- No external dependencies
- Quick testing and development

#### DataReview.tsx
- Interactive table view of extracted data
- Allows sorting, filtering
- Export functionality (CSV, JSON)
- Data validation and editing

#### DynamicDashboard.tsx
- Real-time dashboard with metrics
- Multiple view options
- Customizable layout
- Data synchronization

#### AnomalyTable.tsx
- Displays detected anomalies
- Flags suspicious transactions/entries
- Risk scoring
- Investigation workflow

### 2. **Backend Engines**

#### parsers.py
**Purpose**: Extract data from various file formats

**Key Functions**:
```python
get_parser(file_type)      # Get appropriate parser
extract_tables()           # Extract table data from PDFs
parse_csv()               # Parse CSV files
parse_xlsx()              # Parse Excel files
```

**Supported Formats**:
- PDF (via PDFPlumber)
- CSV (via Pandas)
- XLSX (via Pandas with openpyxl)

#### anomaly_engine.py
**Purpose**: Detect anomalies in financial data

**Key Algorithms**:
- Statistical outlier detection
- Benford's Law validation
- Pattern recognition
- Transaction clustering

**Output**: Anomaly flags with confidence scores

#### unsupervised_engine.py
**Purpose**: Unsupervised learning on transaction data

**Techniques**:
- K-means clustering
- Isolation Forest
- One-class SVM
- Pattern discovery

#### evaluate_engine.py
**Purpose**: Evaluate deal/investment quality

**Metrics**:
- Financial health scores
- Risk assessment
- Growth indicators
- Recommendation scoring

#### insight_generator.py
**Purpose**: Generate AI-powered insights using OpenAI

**Features**:
- Natural language summaries
- Key metric extraction
- Anomaly explanations
- Risk narratives

**Requires**: `OPENAI_API_KEY` environment variable

#### report_generator.py
**Purpose**: Create comprehensive reports

**Output Formats**:
- PDF reports
- JSON data exports
- CSV summaries
- HTML dashboards

### 3. **API Routes**

#### main.py (Production)
**Base URL**: `http://localhost:8000`

**Key Endpoints**:
```
POST   /upload                   - Upload file
GET    /documents                - List documents
GET    /documents/{id}           - Get document details
DELETE /documents/{id}           - Delete document
GET    /extracted-rows/{doc_id}  - Get extracted data
GET    /anomalies/{doc_id}       - Get anomalies
GET    /insights/{doc_id}        - Get AI insights
POST   /reports/{doc_id}         - Generate report
GET    /dashboard                - Dashboard data
```

#### routes/dashboard_mutation.py
**Purpose**: Handle dashboard data mutations

**Endpoints**:
```
POST   /dashboard/mutate         - Update dashboard
POST   /dashboard/save           - Save configuration
GET    /dashboard/schema         - Get schema
```

#### routes/llm_actions.py
**Purpose**: OpenAI integration

**Endpoints**:
```
POST   /llm/summarize           - Generate summary
POST   /llm/analyze             - Analyze data
POST   /llm/extract-insights    - Extract insights
```

#### simple_main.py (Demo)
**Base URL**: `http://localhost:8001`

**Same endpoints as main.py but uses SQLite**

### 4. **Database Schema**

#### documents table
```sql
CREATE TABLE documents (
  id UUID PRIMARY KEY,
  user_id UUID,
  filename TEXT,
  file_type TEXT,
  upload_date TIMESTAMP,
  processing_status TEXT,
  file_path TEXT,
  created_at TIMESTAMP
);
```

#### extracted_rows table
```sql
CREATE TABLE extracted_rows (
  id UUID PRIMARY KEY,
  document_id UUID,
  row_data JSONB,
  table_name TEXT,
  row_index INTEGER,
  extracted_at TIMESTAMP,
  FOREIGN KEY (document_id) REFERENCES documents(id)
);
```

#### anomalies table
```sql
CREATE TABLE anomalies (
  id UUID PRIMARY KEY,
  document_id UUID,
  row_id UUID,
  anomaly_type TEXT,
  confidence FLOAT,
  description TEXT,
  detected_at TIMESTAMP,
  FOREIGN KEY (document_id) REFERENCES documents(id)
);
```

#### insights table
```sql
CREATE TABLE insights (
  id UUID PRIMARY KEY,
  document_id UUID,
  insight_type TEXT,
  content TEXT,
  confidence FLOAT,
  generated_at TIMESTAMP,
  FOREIGN KEY (document_id) REFERENCES documents(id)
);
```

---

## Setup & Installation

### Prerequisites
- **Node.js** 20.0.0 or higher
- **npm** 8.19.2 or higher
- **Python** 3.11.6
- **Git**
- **Supabase account** (for production)
- **OpenAI API key** (optional, for AI features)

### Step 1: Clone Repository
```bash
git clone https://github.com/MbaksKwatu/Tunnel.git
cd Tunnel
```

### Step 2: Install Frontend Dependencies
```bash
npm install
```

### Step 3: Setup Backend

#### Create Virtual Environment
```bash
cd backend
python3.11 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

#### Install Python Dependencies
```bash
pip install -r requirements.txt
```

### Step 4: Environment Configuration

#### Development (.env.local)
```bash
# Supabase
NEXT_PUBLIC_SUPABASE_URL=your_supabase_url
NEXT_PUBLIC_SUPABASE_ANON_KEY=your_anon_key

# Backend
SUPABASE_URL=your_supabase_url
SUPABASE_SERVICE_ROLE_KEY=your_service_role_key

# OpenAI (optional)
OPENAI_API_KEY=your_openai_key

# Backend Port
BACKEND_PORT=8000
```

#### Copy Template
```bash
cp .env.example .env.local
# Then edit with your values
```

### Step 5: Start Development Servers

#### Terminal 1: Frontend
```bash
npm run dev
# Accessible at http://localhost:3000
```

#### Terminal 2: Backend (Production Mode)
```bash
cd backend
source venv/bin/activate
python main.py
# API at http://localhost:8000
```

#### Or Demo Mode (SQLite)
```bash
cd backend
source venv/bin/activate
python simple_main.py
# API at http://localhost:8001
```

### Step 6: Access Application
- **Main App**: http://localhost:3000
- **Demo Mode**: http://localhost:3000/simple-page
- **API Docs**: http://localhost:8000/docs (Swagger UI)

---

## Deployment

### Render Deployment

#### Prerequisites
- Render account
- Connected GitHub repository
- Environment variables configured

#### Configuration Files
```
render.yaml           - Service configuration
Dockerfile           - Container definition
runtime.txt          - Python version (3.11.6)
requirements.txt     - Dependencies (pinned versions)
Procfile            - Process configuration
```

#### Deploy Steps

1. **Push to GitHub**
   ```bash
   git push origin main
   ```

2. **Connect Repository**
   - Go to render.com
   - Connect your GitHub repository

3. **Create Web Service**
   - Select the repository
   - Render auto-detects configuration from `render.yaml`

4. **Configure Environment**
   - Add environment variables in Render dashboard
   - Include `SUPABASE_SERVICE_ROLE_KEY`, `OPENAI_API_KEY`, etc.

5. **Deploy**
   - Render automatically deploys on push to main
   - Monitor build logs in dashboard

#### Key Configuration (render.yaml)
```yaml
services:
  - type: web
    name: Tunnel
    runtime: python
    buildCommand: pip install -r backend/requirements.txt
    startCommand: cd backend && uvicorn main:app --host 0.0.0.0
    envVars:
      - key: SUPABASE_SERVICE_ROLE_KEY
        sync: false
      - key: OPENAI_API_KEY
        sync: false
```

### Local Deployment (Docker)

```bash
# Build image
docker build -t fundiq-tunnel .

# Run container
docker run -p 3000:3000 -p 8000:8000 \
  -e SUPABASE_URL=your_url \
  -e SUPABASE_SERVICE_ROLE_KEY=your_key \
  fundiq-tunnel
```

---

## Environment Configuration

### Required Variables (Production)
```
NEXT_PUBLIC_SUPABASE_URL           # Your Supabase project URL
NEXT_PUBLIC_SUPABASE_ANON_KEY      # Supabase anonymous key
SUPABASE_URL                       # Backend Supabase URL
SUPABASE_SERVICE_ROLE_KEY          # Backend service role key (admin)
OPENAI_API_KEY                     # OpenAI API key (for AI features)
```

### Optional Variables
```
BACKEND_PORT                       # Backend server port (default: 8000)
LOG_LEVEL                          # Logging level (default: INFO)
MAX_FILE_SIZE                      # Max upload size (default: 100MB)
DATABASE_URL                       # Alternative database connection
```

### Getting Credentials

#### Supabase
1. Create account at supabase.com
2. Create new project
3. Go to Settings → API
4. Copy Project URL and keys
5. Enable RLS policies

#### OpenAI
1. Create account at openai.com
2. Go to API keys section
3. Create new API key
4. Copy and store securely

---

## Key Files & Their Purposes

### Configuration Files

| File | Purpose |
|------|---------|
| `package.json` | Node.js dependencies and scripts |
| `tsconfig.json` | TypeScript configuration |
| `next.config.js` | Next.js configuration |
| `tailwind.config.ts` | Tailwind CSS configuration |
| `requirements.txt` | Python dependencies (pinned versions) |
| `runtime.txt` | Python version specification (3.11.6) |
| `.env.local` | Local environment variables |
| `render.yaml` | Render deployment configuration |
| `railway.toml` | Railway deployment configuration |

### Frontend Entry Points

| File | Purpose |
|------|---------|
| `app/page.tsx` | Main application page |
| `app/simple-page.tsx` | Demo page entry |
| `app/layout.tsx` | Root layout wrapper |

### Backend Entry Points

| File | Purpose |
|------|---------|
| `backend/main.py` | Production backend (Supabase) |
| `backend/simple_main.py` | Demo backend (SQLite) |

### Critical Libraries

| File | Purpose |
|------|---------|
| `lib/supabase.ts` | Supabase client initialization |
| `lib/types.ts` | TypeScript type definitions |
| `backend/parsers.py` | Document parsing logic |
| `backend/anomaly_engine.py` | Anomaly detection |

---

## API Endpoints

### File Operations
```
POST   /upload                    - Upload and parse file
GET    /documents                 - List all documents
GET    /documents/{id}            - Get document details
DELETE /documents/{id}            - Delete document
GET    /download/{id}             - Download original file
```

### Data Extraction
```
GET    /extracted-rows/{doc_id}   - Get extracted table rows
GET    /extracted-rows/{doc_id}?table={name} - Filter by table name
POST   /extracted-rows/{doc_id}   - Save extracted data
```

### Analysis
```
GET    /anomalies/{doc_id}        - Get detected anomalies
GET    /insights/{doc_id}         - Get AI-generated insights
GET    /evaluate/{doc_id}         - Get evaluation results
GET    /unsupervised/{doc_id}     - Get clustering results
```

### Reporting
```
POST   /reports/{doc_id}          - Generate report
GET    /reports/{doc_id}          - Get report
POST   /dashboard/mutate          - Update dashboard
GET    /dashboard                 - Get dashboard data
```

### Health
```
GET    /health                    - Health check
GET    /docs                      - API documentation (Swagger)
GET    /redoc                     - Alternative API docs
```

---

## Database Schema

### Core Tables

#### documents
Stores uploaded documents metadata
```
- id: UUID (primary key)
- user_id: UUID (foreign key to users)
- filename: VARCHAR
- file_type: VARCHAR (PDF, CSV, XLSX)
- upload_date: TIMESTAMP
- processing_status: VARCHAR (pending, processing, complete, error)
- file_size: INTEGER
- created_at: TIMESTAMP
- updated_at: TIMESTAMP
```

#### extracted_rows
Stores data extracted from documents
```
- id: UUID (primary key)
- document_id: UUID (foreign key)
- table_index: INTEGER
- row_index: INTEGER
- row_data: JSONB
- table_name: VARCHAR
- extracted_at: TIMESTAMP
```

#### anomalies
Stores detected anomalies
```
- id: UUID (primary key)
- document_id: UUID (foreign key)
- row_id: UUID (foreign key to extracted_rows)
- anomaly_type: VARCHAR
- severity: VARCHAR (low, medium, high)
- confidence: FLOAT (0-1)
- description: TEXT
- details: JSONB
- detected_at: TIMESTAMP
```

#### insights
Stores AI-generated insights
```
- id: UUID (primary key)
- document_id: UUID (foreign key)
- insight_type: VARCHAR
- content: TEXT
- confidence: FLOAT (0-1)
- tags: VARCHAR[] (array of tags)
- generated_at: TIMESTAMP
```

### RLS Policies
All tables use Row Level Security with service role access.
- Service role: Full access (for backend)
- User role: Limited access (own data)

---

## Frontend Pages

### 1. **Home Page** (`/`)
- Feature showcase
- Quick start guide
- Links to other pages
- File upload interface

### 2. **Simple Page** (`/simple-page`)
- Demo version using SQLite
- No Supabase required
- Same functionality as main
- Great for testing

### 3. **Dashboard** (`/dashboard`)
- Real-time metrics display
- Multiple chart types
- Data visualization
- Customizable layout
- Export options

### 4. **Reports** (`/reports`)
- Report generation
- Multiple templates
- PDF export
- Scheduled reports

### 5. **Actions** (`/actions`)
- Bulk operations
- Data export
- Batch processing
- Rule application

### 6. **Evaluate** (`/actions/evaluate`)
- Deal evaluation tool
- Scoring system
- Risk assessment
- Comparison view

### 7. **Companion** (`/companion`)
- AI chat interface
- Ask questions about data
- Get recommendations
- Requires OpenAI key

### 8. **Debug** (`/debug`)
- Development tools
- API testing
- Data inspection
- Logs viewer

---

## Troubleshooting

### Common Issues

#### 1. **Supabase Connection Failed**
```
Error: Failed to connect to Supabase
```
**Solution**:
- Verify `SUPABASE_URL` is correct
- Check `SUPABASE_SERVICE_ROLE_KEY` is valid
- Ensure RLS policies are configured
- Test with: `curl -H "Authorization: Bearer KEY" URL/rest/v1/documents`

#### 2. **Python 3.13 Used Instead of 3.11.6**
```
==> Using Python version 3.13.4 (default)
```
**Solution**:
- Ensure `runtime.txt` exists at repository root
- Content must be exactly: `python-3.11.6`
- Commit and push to trigger rebuild
- Render may cache old Python version

#### 3. **Pandas/NumPy Installation Fails**
```
ERROR: Could not build wheels for pandas
```
**Solution**:
- Verify Python 3.11.6 is being used (not 3.13)
- Ensure binary wheels available for your Python version
- Pin exact versions in requirements.txt
- Use: `pip install --only-binary :all: pandas==2.2.2`

#### 4. **OpenAI Features Not Working**
```
Error: OPENAI_API_KEY not found
```
**Solution**:
- Add `OPENAI_API_KEY` to environment variables
- Get key from openai.com/api-keys
- Ensure key has appropriate permissions
- Check key hasn't reached rate limit

#### 5. **File Upload Timeout**
```
Error: Request timeout
```
**Solution**:
- Check file size (should be < 100MB)
- Verify backend is running
- Check CORS settings in backend
- Increase timeout in axios config

#### 6. **Database Errors**
```
Error: RLS policy violation
```
**Solution**:
- Verify service role key is being used
- Check RLS policies in Supabase dashboard
- Run: `fix_supabase.sql` to reset policies
- Ensure user ID matches authenticated user

### Debug Commands

```bash
# Check backend health
curl http://localhost:8000/health

# View API documentation
curl http://localhost:8000/docs

# Test file upload
curl -X POST http://localhost:8000/upload \
  -F "file=@sample.csv"

# Check database connection (requires auth)
curl -H "Authorization: Bearer YOUR_KEY" \
  http://localhost:8000/documents

# View logs
tail -f backend/debug.log

# Run tests
cd backend
python -m pytest tests/

# Check Python version
python --version

# Verify dependencies
pip list | grep -E "fastapi|pandas|numpy"
```

### Performance Optimization

1. **Slow PDF Parsing**
   - Pre-process large PDFs
   - Use async file processing
   - Enable caching

2. **High Memory Usage**
   - Reduce batch size
   - Process files sequentially
   - Monitor with `memory_profiler`

3. **Database Queries Slow**
   - Add indexes on common fields
   - Use pagination
   - Cache results

---

## Security Considerations

### Best Practices

1. **Environment Variables**
   - Never commit `.env` files
   - Use `.env.local` for development
   - Rotate keys regularly
   - Use Render/Railway secrets manager

2. **API Security**
   - Implement rate limiting
   - Use HTTPS in production
   - Validate all inputs
   - Implement CORS properly

3. **Database Security**
   - Enable RLS on all tables
   - Use service role carefully
   - Audit user access
   - Regular backups

4. **File Uploads**
   - Validate file types
   - Limit file sizes
   - Scan for malware
   - Store securely

---

## Additional Resources

- **API Docs**: http://localhost:8000/docs (Swagger UI)
- **Supabase Docs**: https://supabase.com/docs
- **Next.js Docs**: https://nextjs.org/docs
- **FastAPI Docs**: https://fastapi.tiangolo.com
- **Render Docs**: https://render.com/docs

---

## Support & Contribution

For issues, questions, or contributions:
- GitHub Issues: https://github.com/MbaksKwatu/Tunnel/issues
- Email: support@fundiq.com
- Documentation: See `/docs` folder

---

**Last Updated**: December 10, 2025
**Version**: 2.0.0
**License**: MIT (if applicable)
