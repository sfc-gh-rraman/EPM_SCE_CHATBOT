# 🚀 SCE EPM Chatbot Deployment Guide

## Overview

SCE EPM Contract Chatbot is deployed as a full-stack application on **Snowpark Container Services (SPCS)**. This guide covers:
1. Prerequisites
2. Local development
3. SPCS deployment
4. Troubleshooting

---

## Prerequisites

### Snowflake Account
- Snowflake account with **Cortex AI** enabled
- **ACCOUNTADMIN** role (or delegated privileges)
- SPCS enabled in your region

### Local Tools
```bash
# Required
brew install node           # v18+
brew install python@3.11    # Python 3.11+
brew install docker         # Docker Desktop

# Snowflake CLI
pip install snowflake-cli-labs
snow --version              # Verify installation
```

### Configure Snowflake Connection
```bash
# Create connection (one-time setup)
snow connection add
# Name: myconnection (or any name you prefer)
# Account: your-account.snowflakecomputing.com
# User: your_username
# Authenticator: externalbrowser (recommended)

# Test connection
snow connection test -c myconnection

# Set as default (optional)
snow connection set-default myconnection
```

---

## Quick Start

### Option 1: Full Deployment (Recommended)
```bash
# From the project root (construction_capital_delivery/)
cd construction_capital_delivery

# Deploy everything: DDL + Data + Cortex + Notebooks
./deploy.sh all

# Then deploy SPCS service
cd copilot/deploy
./deploy.sh
```

### Option 2: Step-by-Step
```bash
# 1. Deploy database and data (from project root)
./deploy.sh

# 2. Deploy Cortex Search services
snow sql -f cortex/deploy_search.sql

# 3. Create Cortex Agent (via Snowsight UI)
# See "Cortex Agent Setup" section below

# 4. Deploy SPCS service
cd copilot/deploy
./deploy.sh
```

---

## Local Development

### Backend (FastAPI)
```bash
cd copilot/backend

# Create virtual environment
python -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Set environment variables (update with your values)
export SNOWFLAKE_ACCOUNT="<your-account>"
export SNOWFLAKE_USER="<your-username>"
export SNOWFLAKE_DATABASE="SCE_EPM_DB"
export SNOWFLAKE_SCHEMA="CONTRACTS"
export SNOWFLAKE_WAREHOUSE="SCE_EPM_WH"

# Run server
uvicorn api.main:app --reload --port 8000
```

### Frontend (React)
```bash
cd copilot/frontend

# Install dependencies
npm install

# Run dev server
npm run dev
# Opens at http://localhost:5173
```

### Full Stack (Local)
```bash
# Terminal 1: Backend
cd copilot/backend && uvicorn api.main:app --reload --port 8000

# Terminal 2: Frontend
cd copilot/frontend && npm run dev
```

---

## SPCS Deployment

### 1. Setup Infrastructure
```bash
cd copilot/deploy

# Create compute pool and image repository
./deploy.sh setup
```

This creates:
- `SCE_EPM_DB.SPCS` schema
- `SCE_EPM_IMAGES` image repository
- `SCE_EPM_COMPUTE_POOL` compute pool (CPU_X64_S)

### 2. Build Docker Image
```bash
# Build for linux/amd64 (required for SPCS)
./deploy.sh build
```

### 3. Push to Snowflake Registry
```bash
# Login and push
./deploy.sh push
```

### 4. Deploy Service
```bash
# Create/update SPCS service
./deploy.sh deploy
```

### 5. Get Service URL
```bash
# Check status and get URL
./deploy.sh status
```

Or in Snowsight:
```sql
SHOW ENDPOINTS IN SERVICE SCE_EPM_DB.SPCS.SCE_EPM_SERVICE;
```

---

## Cortex Agent Setup

The Cortex Agent must be created via Snowsight UI (not SQL).

### Step 1: Open Snowsight
Navigate to **AI & ML → Cortex Agents**

### Step 2: Create Agent
Click **+ Create** and configure:

| Field | Value |
|-------|-------|
| Name | `SCE_EPM_CONTRACT_AGENT` |
| Database | `SCE_EPM_DB` |
| Schema | `CONTRACTS` |
| Model | `mistral-large` |

### Step 3: Add Instructions
```
You are ATLAS, an AI assistant for capital project portfolio management.

You help project managers, executives, and analysts understand:
- Portfolio health (CPI, SPI, EAC)
- Change order patterns and hidden scope gaps
- Vendor performance and risk
- Schedule impacts and critical path

HIDDEN DISCOVERY: When asked about patterns, look for the "electrical grounding" 
scope gap - 150+ small COs totaling $1.45M across 12 projects from a single 
specification template error.

Always provide context about aggregate portfolio impact, not just individual items.
```

### Step 4: Add Tools

**Tool 1: Cortex Analyst**
- Type: `cortex_analyst_text_to_sql`
- Name: `data_analyst`
- Semantic Model: `@SCE_EPM_DB.CORTEX.SEMANTIC_MODELS/capital_semantic_model.yaml`

**Tool 2: Cortex Search (Change Orders)**
- Type: `cortex_search`
- Name: `co_search`
- Service: `SCE_EPM_DB.DOCS.CO_SEARCH_SERVICE`

**Tool 3: Cortex Search (Contracts)**
- Type: `cortex_search`
- Name: `contract_search`
- Service: `SCE_EPM_DB.DOCS.CONTRACT_SEARCH_SERVICE`

### Step 5: Grant Access
```sql
GRANT USAGE ON CORTEX AGENT SCE_EPM_DB.CONTRACTS.SCE_EPM_CONTRACT_AGENT 
    TO ROLE SCE_EPM_APP_ROLE;
```

---

## Deploy Script Commands

```bash
./deploy.sh              # Full deployment (build + push + deploy)
./deploy.sh setup        # Create compute pool and image repository
./deploy.sh build        # Build Docker image only
./deploy.sh push         # Push to Snowflake registry only
./deploy.sh deploy       # Deploy/update service only
./deploy.sh status       # Check service status and URL
./deploy.sh logs         # View service logs
./deploy.sh stop         # Stop the service
```

---

## Troubleshooting

### "Image not found" Error
```bash
# Verify image exists in registry
snow sql -q "SHOW IMAGES IN IMAGE REPOSITORY SCE_EPM_DB.SPCS.SCE_EPM_IMAGES;"

# Rebuild and push
./deploy.sh build
./deploy.sh push
```

### Service Won't Start
```bash
# Check logs
./deploy.sh logs

# Common issues:
# 1. Missing environment variables
# 2. Compute pool not running
# 3. Image architecture mismatch (must be linux/amd64)
```

### "Token expired" in Logs
The SPCS token auto-refreshes, but connections may timeout. The app includes auto-reconnection logic. If persistent:
```sql
-- Restart service
ALTER SERVICE SCE_EPM_DB.SPCS.SCE_EPM_SERVICE SUSPEND;
ALTER SERVICE SCE_EPM_DB.SPCS.SCE_EPM_SERVICE RESUME;
```

### Cortex Agent Returns 404
The agent doesn't exist. Create it via Snowsight UI (see above).

### Cortex Search Returns Empty
```sql
-- Verify search service is active
SHOW CORTEX SEARCH SERVICES IN DATABASE SCE_EPM_DB;

-- Verify data exists
SELECT COUNT(*) FROM SCE_EPM_DB.DOCS.CO_NARRATIVES;

-- Rebuild if needed
-- Run cortex/deploy_search.sql
```

### Map Tiles Not Loading
SPCS needs external network access for OpenStreetMap tiles:
```sql
-- Create network rule and integration (run as ACCOUNTADMIN)
CREATE OR REPLACE NETWORK RULE SCE_EPM_NET_RULE
    MODE = EGRESS TYPE = HOST_PORT
    VALUE_LIST = ('tile.openstreetmap.org:443', 'a.tile.openstreetmap.org:443', 
                  'b.tile.openstreetmap.org:443', 'c.tile.openstreetmap.org:443');

CREATE OR REPLACE EXTERNAL ACCESS INTEGRATION SCE_EPM_NET_ACCESS
    ALLOWED_NETWORK_RULES = (SCE_EPM_NET_RULE) ENABLED = TRUE;

-- Add to service (in deploy.sh or manually)
-- EXTERNAL_ACCESS_INTEGRATIONS = (SCE_EPM_NET_ACCESS)
```

---

## Environment Variables (SPCS)

These are set automatically in `service_spec.yaml`:

| Variable | Value | Description |
|----------|-------|-------------|
| `SNOWFLAKE_DATABASE` | `SCE_EPM_DB` | Database name |
| `SNOWFLAKE_SCHEMA` | `CONTRACTS` | Schema name |
| `SNOWFLAKE_WAREHOUSE` | `SCE_EPM_WH` | Warehouse for queries |
| `SNOWFLAKE_HOST` | Auto-detected | Account URL |

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    SPCS Container                        │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐ │
│  │   Nginx     │───▶│   FastAPI   │───▶│  Snowflake  │ │
│  │   (8080)    │    │   Backend   │    │   Cortex    │ │
│  └─────────────┘    └─────────────┘    └─────────────┘ │
│         │                                               │
│  ┌─────────────┐                                        │
│  │    React    │                                        │
│  │   Frontend  │                                        │
│  └─────────────┘                                        │
└─────────────────────────────────────────────────────────┘
```

- **Nginx**: Reverse proxy, serves React static files, routes `/api/*` to FastAPI
- **FastAPI**: Python backend, connects to Snowflake via Snowpark
- **React**: TypeScript frontend with Tailwind CSS
- **Cortex**: AI services (LLM, Search, Analyst, Agents)

---

## Support

For issues:
1. Check service logs: `./deploy.sh logs`
2. Verify Snowflake connectivity: `snow connection test`
3. Check Cortex services in Snowsight

---

*Built on Snowflake Snowpark Container Services*
