# SCE EPM Contract Chatbot

Conversational interface over Southern California Edison's Energy Portfolio
Management contract book — Power Purchase Agreements (PPAs), Resource Adequacy
(RA) contracts, tolling agreements, and their amendments.

Built entirely on **Snowflake Cortex** (Analyst + Search + Agents) with a
FastAPI / React front end deployable to Snowpark Container Services.

> **Reference architecture cloned from** the ATLAS Capital Delivery
> Intelligence Platform (`construction_capital_delivery`).

---

## What it answers

| # | Question                                                                                  | How                                                         |
|---|-------------------------------------------------------------------------------------------|-------------------------------------------------------------|
| 1 | How many amendments does a contract have? What does each one cover?                       | Cortex Analyst over `ATOMIC.AMENDMENT` (filename-parsed)    |
| 2 | What changed in a specific amendment?                                                     | Hybrid: Analyst → amendment row + Search → clause chunks    |
| 3 | List contracts with a specific curtailment term                                           | Cortex Analyst over `CONTRACT_CURTAILMENT_V`                |
| 4 | List contracts with capacity > 10 MW                                                      | Cortex Analyst over `CONTRACT_SUMMARY_V`                    |
| 5 | Extract contracts with similar concept (product deficiency, RA delivery, EANEP, etc.)     | `compare_clause_across_contracts` custom tool + Search      |
| 6 | Paid by SCE meter but have an ISO meter                                                   | Cortex Analyst over `METERING_MISMATCH_V`                   |

## Cortex Agent — `SCE_EPM_DB.CORTEX.SCE_EPM_CONTRACT_AGENT`

The single agent has **7 tools** that the orchestrator picks between:

| Tool                              | Type                          | Purpose                                                    |
|-----------------------------------|-------------------------------|------------------------------------------------------------|
| `contract_data`                   | `cortex_analyst_text_to_sql`  | NL → SQL over the semantic model (Q1/Q3/Q4/Q6 verified)    |
| `contract_clause_search`          | `cortex_search`               | Clause-level RAG over base contracts + amendments          |
| `amendment_file_search`           | `cortex_search`               | Search amendment filenames + summaries (Q1 enumerate)      |
| `parse_amendment_filename`        | `generic` (SQL UDF)           | Deconstruct a PDF filename into structured fields          |
| `get_contract_360`                | `generic` (SQL procedure)     | 360-degree dossier for a single contract                   |
| `compare_clause_across_contracts` | `generic` (SQL procedure)     | Q5 concept extraction grouped by approach                  |
| `data_to_chart`                   | `data_to_chart`               | Vega-Lite chart spec generation                            |

---

## Repo layout

```
epm_sce_chatbot/
├── ddl/                                  Database, atomic tables, views
│   ├── 001_database.sql
│   ├── 002_atomic_tables.sql
│   └── 003_views.sql
├── scripts/
│   ├── generate_synthetic_data.py        25 contracts, 53 amendments, 422 chunks
│   └── load_data.sql                     PUT + INSERT FROM SELECT
├── data/synthetic/                       parquet artifacts
├── cortex/
│   ├── sce_epm_semantic_model.yaml       Analyst model (Q1/Q3/Q4/Q6 verified queries)
│   ├── deploy_search.sql                 CONTRACT_CLAUSE_SEARCH + AMENDMENT_FILE_SEARCH
│   └── sce_epm_agent.json                Agent definition
├── copilot/
│   ├── backend/                          FastAPI + Cortex Agent SSE client
│   ├── frontend/                         React 18 + Vite + Tailwind
│   └── deploy/                           Dockerfile + nginx + service_spec.yaml
└── deploy.sh                             One-shot Snowflake deploy
```

---

## Quick start

### Prerequisites

* `snow` CLI configured with a connection (default `demo`)
* Python 3.11+ with `pandas`, `pyarrow`, `numpy`
* For the front end: Node 20+

### 1. Deploy to Snowflake

```bash
./deploy.sh                                   # default connection 'demo'
./deploy.sh -c my_connection                  # custom connection
./deploy.sh --only-data                       # re-load synthetic data
```

The script:

1. Creates `SCE_EPM_DB` with schemas `RAW / ATOMIC / CONTRACTS / DOCS / CORTEX / SPCS`
2. Generates parquet → uploads to `@RAW.DATA_STAGE` → loads into `ATOMIC.*`
3. Creates `CONTRACTS.*` analytics views
4. Uploads the semantic model YAML to `@CORTEX.SEMANTIC_MODELS`
5. Creates the two Cortex Search services (`CONTRACT_CLAUSE_SEARCH`,
   `AMENDMENT_FILE_SEARCH`)
6. Deploys 3 custom tools (`PARSE_AMENDMENT_FILENAME`, `GET_CONTRACT_360`,
   `COMPARE_CLAUSE_ACROSS_CONTRACTS`) into `SCE_EPM_DB.CORTEX`
7. Creates the Cortex Agent `SCE_EPM_CONTRACT_AGENT` with all 7 tools wired
   together (run `snow sql -c <conn> -f cortex/deploy_agent.sql`)

### 2. Verify

```sql
-- Q1
SELECT * FROM SCE_EPM_DB.CONTRACTS.AMENDMENT_TIMELINE_V LIMIT 5;

-- Q3
SELECT * FROM SCE_EPM_DB.CONTRACTS.CONTRACT_CURTAILMENT_V WHERE CURTAILMENT_TYPE='ECONOMIC';

-- Q4
SELECT * FROM SCE_EPM_DB.CONTRACTS.CONTRACT_SUMMARY_V WHERE CAPACITY_MW > 10 ORDER BY CAPACITY_MW DESC;

-- Q5/Q2 — clause search
SELECT * FROM TABLE(SCE_EPM_DB.DOCS.CONTRACT_CLAUSE_SEARCH(
    QUERY  => 'remedy if seller fails to deliver Resource Adequacy capacity',
    LIMIT  => 10
));

-- Q6
SELECT * FROM SCE_EPM_DB.CONTRACTS.METERING_MISMATCH_V;
```

### 3. Run the chatbot locally

```bash
# Backend
cd copilot/backend
pip install -r requirements.txt
SNOWFLAKE_CONNECTION_NAME=demo \
SNOWFLAKE_DATABASE=SCE_EPM_DB \
uvicorn api.main:app --reload --port 8080

# Frontend
cd copilot/frontend
npm install
npm run dev   # → http://localhost:5173
```

### 4. Deploy to SPCS

```bash
cd copilot/deploy
./deploy.sh -c demo
```

See `copilot/deploy/DEPLOYMENT_GUIDE.md` for full container deployment details.

---

## Data model summary

```
COUNTERPARTY ── 1:N ── CONTRACT ── 1:N ── AMENDMENT
                          │
                          ├── 1:1 ── METERING_CONFIG
                          └── 1:N ── CONTRACT_DOCUMENT_CHUNK
                                          │
                                          ├ CLAUSE_TYPE  (CURTAILMENT | DELIVERY_FAILURE |
                                          │              RA_REMEDY | METERING | EANEP |
                                          │              DEGRADATION | PRICING | TERM | …)
                                          └ AMENDMENT_ID (NULL for base contract)
```

Amendment filenames follow the spec:

```
{CONTRACT_ID}_{YYYY-MM-DD}_{COUNTERPARTY}_{DOC_TYPE_FREE_TEXT}.pdf
e.g.  CTR-001_2022-09-13_Mojave_First_Amendment.pdf
```

Both `AMENDMENT.DOC_TYPE` and `CONTRACT_DOCUMENT_CHUNK.DOC_TYPE` carry the
parsed document category (AMENDMENT / RESTATEMENT / SIDE_LETTER / NOTICE),
which is exposed as a filterable attribute on the search service.

---

## Synthetic dataset stats

| Entity                      | Rows |
|-----------------------------|-----:|
| counterparties              |   15 |
| contracts                   |   25 |
| amendments                  |   53 |
| metering configurations     |   25 |
| contract document chunks    |  422 |
| Q3 curtailment contracts    |   15 |
| Q4 contracts > 10 MW        |   23 |
| Q6 metering mismatches      |   10 |

---

## Citation behaviour

Every chatbot response surfaces:

* `CONTRACT_ID` (and `AMENDMENT_ID` if relevant)
* `SECTION_TITLE` and `PAGE_NUMBER` for clause-level answers
* `SOURCE_FILE` (the original PDF filename) so the user can open the document
* For Cortex Analyst answers, the SQL is logged and the structured result is
  rendered as a markdown table
