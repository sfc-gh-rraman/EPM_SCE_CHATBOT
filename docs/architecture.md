# SCE EPM Contract Intelligence — Architecture Diagrams

## 1. System Architecture (High-Level)

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                          SNOWPARK CONTAINER SERVICES (SPCS)                          │
│                                                                                     │
│  ┌──────────────┐     ┌──────────────────┐     ┌─────────────────────────────────┐  │
│  │              │     │                  │     │                                 │  │
│  │   nginx      │────▶│  FastAPI Backend  │────▶│   Snowflake Cortex Agent        │  │
│  │   :8080      │     │  :8000           │     │   (SCE_EPM_CONTRACT_AGENT)      │  │
│  │              │     │                  │     │                                 │  │
│  │  ┌────────┐  │     │  • /api/chat/    │     │   7 Tools:                      │  │
│  │  │ React  │  │     │    stream (SSE)  │     │   ├─ cortex_analyst (text→SQL)  │  │
│  │  │  SPA   │  │     │  • /api/portfolio│     │   ├─ contract_clause_search     │  │
│  │  │ 8 tabs │  │     │  • /api/contracts│     │   ├─ amendment_file_search      │  │
│  │  └────────┘  │     │  • /api/clauses  │     │   ├─ parse_amendment_filename   │  │
│  │              │     │  • /api/daily-   │     │   ├─ get_contract_360           │  │
│  │              │     │    brief         │     │   ├─ compare_clause_across_     │  │
│  └──────────────┘     │  • /api/resource-│     │   │  contracts                  │  │
│                       │    map           │     │   └─ data_to_chart              │  │
│                       └──────────────────┘     └─────────────────────────────────┘  │
│                                                                                     │
└─────────────────────────────────────────────────────────────────────────────────────┘
         │                        │                          │
         │ OAuth                  │ snow sql                 │ REST API
         ▼                        ▼                          ▼
┌─────────────────┐    ┌────────────────────┐    ┌──────────────────────────┐
│   Browser       │    │   Snowflake        │    │   Cortex AI Services     │
│   (Prisma/SSO)  │    │   SCE_EPM_DB       │    │                          │
│                 │    │                    │    │   • PARSE_DOCUMENT (OCR) │
└─────────────────┘    │   5 Schemas:       │    │   • SPLIT_TEXT           │
                       │   RAW / ATOMIC /   │    │   • EMBED_TEXT           │
                       │   CONTRACTS / DOCS │    │   • AI_CLASSIFY          │
                       │   / CORTEX / SPCS  │    │   • COMPLETE (LLM)       │
                       └────────────────────┘    └──────────────────────────┘
```

## 2. Data Pipeline (PDF Ingestion → Agent-Ready)

```
  CPUC Public PPAs                    Snowflake RAW                         ATOMIC
  (files.cpuc.ca.gov)                 Schema                                Schema
 ─────────────────────               ─────────────                         ──────────

 ┌───────────────────┐    PUT 580    ┌──────────────┐                     ┌──────────────┐
 │  580 PDF files    │───────────────▶│  PDF_STAGE   │                     │  CONTRACT    │
 │  (1.67 GB)        │   (SSE enc.)  │  (internal)  │                     │  (122 rows)  │
 └───────────────────┘               └──────┬───────┘                     └──────────────┘
                                            │                                    │
                                            │ PARSE_DOCUMENT                     │
                                            │ (mode: OCR)                        │
                                            ▼                                    │
                                     ┌──────────────┐                     ┌──────────────┐
                                     │  PDF_TEXT     │                     │  AMENDMENT   │
                                     │  (580 rows)  │                     │  (360 rows)  │
                                     │  106M chars  │                     └──────────────┘
                                     └──────┬───────┘                            │
                                            │                                    │
                                            │ SPLIT_TEXT_RECURSIVE_CHARACTER      │
                                            │ (1800 chars, 200 overlap)          │
                                            ▼                                    │
                                     ┌──────────────┐                     ┌──────────────┐
                                     │  CHUNKS      │◀────────────────────│ COUNTERPARTY │
                                     │  (58,088)    │   JOIN on           │  (315 rows)  │
                                     └──────┬───────┘   CONTRACT_ID       └──────────────┘
                                            │
                                            │ Heuristic CLAUSE_TYPE
                                            │ (REGEXP_LIKE + CONTAINS)
                                            ▼
                                     ┌──────────────┐         ┌─────────────────────────┐
                                     │  Classified  │────────▶│  DOCS.CLAUSES           │
                                     │  Chunks      │         │  (58,088 denormalized)  │
                                     │              │         └───────────┬─────────────┘
                                     │  CURTAILMENT │                     │
                                     │  = 2,930     │                     │ Cortex Search
                                     │  TERMINATION │                     │ (TARGET_LAG='1h')
                                     │  = 63        │                     ▼
                                     │  DELIVERY_   │         ┌─────────────────────────┐
                                     │  FAILURE = 46│         │  CONTRACT_CLAUSE_SEARCH │
                                     │  METERING    │         │  AMENDMENT_FILE_SEARCH  │
                                     │  = 21        │         └─────────────────────────┘
                                     │  RA_REMEDY   │
                                     │  = 13        │
                                     └──────────────┘
```

## 3. Cortex Agent Tool Orchestration

```
                            ┌──────────────────────────────────────┐
                            │          USER QUESTION                │
                            │  "How does Rio Bravo Fresno handle    │
                            │   curtailment notices?"               │
                            └───────────────────┬──────────────────┘
                                                │
                                                ▼
                            ┌──────────────────────────────────────┐
                            │      CORTEX AGENT ORCHESTRATOR        │
                            │  (SCE_EPM_CONTRACT_AGENT)             │
                            │                                      │
                            │  1. Classify intent                   │
                            │  2. Select tool(s)                    │
                            │  3. Execute & synthesize              │
                            └──┬────────┬────────┬─────────────────┘
                               │        │        │
              ┌────────────────┘        │        └────────────────┐
              ▼                         ▼                         ▼
┌─────────────────────┐  ┌─────────────────────┐  ┌─────────────────────────┐
│  CORTEX ANALYST     │  │  CORTEX SEARCH      │  │  CUSTOM TOOLS           │
│  (text → SQL)       │  │  (semantic RAG)     │  │  (SQL UDF / Procs)      │
│                     │  │                     │  │                         │
│  Semantic Model     │  │  58,088 chunks      │  │  • parse_amendment_     │
│  YAML → verified    │  │  indexed with       │  │    filename             │
│  queries → SQL      │  │  attributes:        │  │  • get_contract_360     │
│                     │  │  • CLAUSE_TYPE      │  │  • compare_clause_      │
│  Best for:          │  │  • CONTRACT_NAME    │  │    across_contracts     │
│  "How many..."      │  │  • SUPPLIER         │  │                         │
│  "List contracts    │  │  • DOC_TYPE         │  │  Best for:              │
│   with..."          │  │                     │  │  Filename parsing,      │
│  "Show me..."       │  │  Best for:          │  │  Full contract dossier, │
│                     │  │  "How does X        │  │  Side-by-side clause    │
└─────────────────────┘  │   handle..."        │  │  comparison             │
                         │  "What are the      │  │                         │
                         │   provisions for.." │  └─────────────────────────┘
                         └─────────────────────┘
                                                │
                                                ▼
                            ┌──────────────────────────────────────┐
                            │         GROUNDED RESPONSE             │
                            │                                      │
                            │  Streamed via SSE with:               │
                            │  • Thinking steps (reasoning)        │
                            │  • Tool invocations (visible)        │
                            │  • Final answer (markdown)           │
                            │  • Source citations (chunk IDs)      │
                            │  • Suggested follow-ups              │
                            └──────────────────────────────────────┘
```

## 4. Frontend Tab Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                        REACT SPA (Vite + Tailwind)                   │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  OVERVIEW                                                           │
│  ├── Dashboard ─────── KPIs, amendment velocity, counterparty dist  │
│  └── Daily Brief ───── AI narrative, risk alerts, recent amendments │
│                                                                     │
│  EXPLORE                                                            │
│  ├── Contract Chat ─── SSE streaming agent (7 tools)                │
│  ├── Contract Deep ─── Per-contract drill: amendments + clause pie  │
│  │   Dive                                                           │
│  └── Contract Search ─ Keyword search + clause type facets          │
│                                                                     │
│  ANALYTICS                                                          │
│  ├── Clause Analytics ─ Distribution, radar, curtailment leaders    │
│  └── Resource Map ──── Counterparty treemap, doc type breakdown     │
│                                                                     │
│  SYSTEM                                                             │
│  └── Architecture ──── Interactive SVG diagram, component modals    │
│                                                                     │
├─────────────────────────────────────────────────────────────────────┤
│  Layout: Dark navy sidebar (nav) + main content area                │
│  Theme:  navy-950 bg, atlas-blue accents, JetBrains Mono font       │
│  Charts: Recharts (Bar, Line, Pie, Radar, Treemap)                  │
└─────────────────────────────────────────────────────────────────────┘
```

## 5. Deployment Architecture (SPCS)

```
┌────────────────────────────────────────────────────────────────────────────┐
│                    SNOWFLAKE ACCOUNT (SFPSCOGS-RRAMAN-AWS-SI)               │
│                                                                            │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │  COMPUTE POOL: SCE_EPM_COMPUTE_POOL (CPU_X64_XS, auto-suspend 1hr) │  │
│  │                                                                      │  │
│  │  ┌────────────────────────────────────────────────────────────────┐  │  │
│  │  │  SERVICE: SCE_EPM_DB.SPCS.SCE_EPM_SERVICE                      │  │  │
│  │  │                                                                │  │  │
│  │  │  Container: sce-epm (python:3.11-slim + node:20 build)         │  │  │
│  │  │  ┌────────┐   ┌──────────┐   ┌──────────────────────────┐     │  │  │
│  │  │  │ nginx  │──▶│ /api/*   │──▶│  uvicorn (FastAPI :8000)  │     │  │  │
│  │  │  │ :8080  │   │          │   │                          │     │  │  │
│  │  │  │        │──▶│ /*       │──▶│  React dist (static)     │     │  │  │
│  │  │  └────────┘   └──────────┘   └──────────────────────────┘     │  │  │
│  │  │                                                                │  │  │
│  │  │  Auth: /snowflake/session/token (auto-mounted)                 │  │  │
│  │  │  EAI:  SCE_EPM_CORTEX_EAI (egress for Cortex Agent REST)      │  │  │
│  │  └────────────────────────────────────────────────────────────────┘  │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
│                                                                            │
│  Public Endpoint: https://jkbm6off-sfpscogs-rraman-aws-si.                 │
│                   snowflakecomputing.app                                    │
│                                                                            │
│  Image Registry:  SCE_EPM_DB.SPCS.SCE_EPM_IMAGES/sce-epm:latest           │
│                                                                            │
└────────────────────────────────────────────────────────────────────────────┘
```

## 6. Database Schema Map

```
SCE_EPM_DB
├── RAW
│   ├── PDF_STAGE ────────── 580 PDFs (1.67 GB, SNOWFLAKE_SSE encrypted)
│   ├── PDF_INVENTORY ────── Filename metadata (project_id, counterparty, date, doc_type)
│   └── PDF_TEXT ─────────── Parsed full text (PARSE_DOCUMENT output, 106M chars)
│
├── ATOMIC
│   ├── CONTRACT ─────────── 122 unique contracts (1 per project_id)
│   ├── COUNTERPARTY ─────── 315 distinct sellers
│   ├── AMENDMENT ────────── 360 amendments/restatements/side letters
│   ├── CONTRACT_DOCUMENT_CHUNK ── 58,088 text chunks (1800 char, classified)
│   └── METERING_CONFIG ──── Payment meter / ISO meter mapping
│
├── CONTRACTS (views)
│   ├── CONTRACT_SUMMARY_V
│   ├── CONTRACT_CURTAILMENT_V
│   ├── AMENDMENT_TIMELINE_V
│   └── METERING_MISMATCH_V
│
├── DOCS
│   ├── CLAUSES ──────────── 58,088 denormalized (chunk + contract + counterparty)
│   ├── AMENDMENT_INDEX ──── 360 searchable amendment records
│   ├── CONTRACT_CLAUSE_SEARCH ── Cortex Search Service (TARGET_LAG='1 hour')
│   └── AMENDMENT_FILE_SEARCH ─── Cortex Search Service (TARGET_LAG='1 hour')
│
├── CORTEX
│   ├── SCE_EPM_CONTRACT_AGENT ── 7-tool Cortex Agent
│   ├── sce_epm_semantic_model.yaml ── Analyst semantic model (on stage)
│   ├── PARSE_AMENDMENT_FILENAME ──── SQL UDF
│   ├── GET_CONTRACT_360 ─────────── Stored Procedure
│   └── COMPARE_CLAUSE_ACROSS_CONTRACTS ── Stored Procedure
│
└── SPCS
    ├── SCE_EPM_IMAGES ───── Image repository
    ├── SCE_EPM_SERVICE ──── Container service (READY)
    └── SCE_EPM_COMPUTE_POOL ── CPU_X64_XS
```
