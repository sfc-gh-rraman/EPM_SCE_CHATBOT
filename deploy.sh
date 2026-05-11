#!/bin/bash
# =============================================================================
# SCE EPM Contract Chatbot — Snowflake Deployment Script
# =============================================================================
# Usage:
#   ./deploy.sh                  # full deploy (DDL + data + Cortex)
#   ./deploy.sh --only-ddl
#   ./deploy.sh --only-data
#   ./deploy.sh --only-cortex
#   ./deploy.sh -c my_connection
# =============================================================================

set -e
set -o pipefail

CONNECTION="${SNOWFLAKE_CONNECTION:-demo}"
DATABASE="${SNOWFLAKE_DATABASE:-SCE_EPM_DB}"
WAREHOUSE="${SNOWFLAKE_WAREHOUSE:-SCE_EPM_WH}"

RED='\033[0;31m'; GREEN='\033[0;32m'; BLUE='\033[0;34m'
YELLOW='\033[1;33m'; CYAN='\033[0;36m'; NC='\033[0m'
msg() { echo -e "${1}${2}${NC}"; }

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

DEPLOY_DDL=true
DEPLOY_DATA=true
DEPLOY_CORTEX=true

while [[ $# -gt 0 ]]; do
    case $1 in
        -c|--connection) CONNECTION="$2"; shift 2 ;;
        --only-ddl)      DEPLOY_DATA=false; DEPLOY_CORTEX=false; shift ;;
        --only-data)     DEPLOY_DDL=false;  DEPLOY_CORTEX=false; shift ;;
        --only-cortex)   DEPLOY_DDL=false;  DEPLOY_DATA=false;   shift ;;
        *) shift ;;
    esac
done

msg "$CYAN" "
=========================================================
  SCE EPM Contract Chatbot — Snowflake Deployment
=========================================================
"
msg "$YELLOW" "Connection : $CONNECTION"
msg "$YELLOW" "Database   : $DATABASE"
msg "$YELLOW" "Warehouse  : $WAREHOUSE"
echo ""

# --------------------------------------------------------------------------
# 1. DDL
# --------------------------------------------------------------------------
if [ "$DEPLOY_DDL" = true ]; then
    msg "$BLUE" "📦 Step 1: Deploying DDL..."
    for sql_file in "$SCRIPT_DIR"/ddl/*.sql; do
        [ -f "$sql_file" ] || continue
        fn=$(basename "$sql_file")
        msg "$GREEN" "  ↳ $fn"
        snow sql -f "$sql_file" -c "$CONNECTION" > /dev/null \
            || msg "$YELLOW" "    (warning: some statements may have failed)"
    done
    msg "$GREEN" "✓ DDL complete\n"
fi

# --------------------------------------------------------------------------
# 2. Synthetic data
# --------------------------------------------------------------------------
if [ "$DEPLOY_DATA" = true ]; then
    msg "$BLUE" "📊 Step 2: Generating + loading synthetic data..."

    if [ ! -f "$SCRIPT_DIR/data/synthetic/contract.parquet" ]; then
        msg "$GREEN" "  ↳ generating parquet files"
        python3 "$SCRIPT_DIR/scripts/generate_synthetic_data.py"
    fi

    msg "$GREEN" "  ↳ uploading parquet files to @SCE_EPM_DB.RAW.DATA_STAGE"
    for f in counterparty contract amendment metering_config contract_document_chunk; do
        snow sql -c "$CONNECTION" -q \
            "PUT 'file://${SCRIPT_DIR}/data/synthetic/${f}.parquet' \
                  @SCE_EPM_DB.RAW.DATA_STAGE OVERWRITE=TRUE AUTO_COMPRESS=FALSE;" \
            > /dev/null
    done

    msg "$GREEN" "  ↳ inserting into ATOMIC tables"
    snow sql -c "$CONNECTION" -f "$SCRIPT_DIR/scripts/load_data.sql" > /dev/null

    msg "$GREEN" "✓ Data loaded\n"
fi

# --------------------------------------------------------------------------
# 3. Cortex (semantic model + search services + agent)
# --------------------------------------------------------------------------
if [ "$DEPLOY_CORTEX" = true ]; then
    msg "$BLUE" "🧠 Step 3: Deploying Cortex artifacts..."

    msg "$GREEN" "  ↳ uploading semantic model YAML"
    snow sql -c "$CONNECTION" -q \
        "PUT 'file://${SCRIPT_DIR}/cortex/sce_epm_semantic_model.yaml' \
              @SCE_EPM_DB.CORTEX.SEMANTIC_MODELS OVERWRITE=TRUE AUTO_COMPRESS=FALSE;" \
        > /dev/null

    msg "$GREEN" "  ↳ creating Cortex Search services"
    snow sql -c "$CONNECTION" -f "$SCRIPT_DIR/cortex/deploy_search.sql" > /dev/null

    msg "$GREEN" "  ↳ deploying custom SQL tools (UDF + procedures)"
    snow sql -c "$CONNECTION" -f "$SCRIPT_DIR/cortex/deploy_custom_tools.sql" > /dev/null

    msg "$GREEN" "  ↳ creating Cortex Agent"
    snow sql -c "$CONNECTION" -f "$SCRIPT_DIR/cortex/deploy_agent.sql" > /dev/null

    msg "$GREEN" "✓ Cortex artifacts deployed (search + custom tools + agent)\n"
fi

msg "$CYAN" "
=========================================================
  ✓ Deployment complete
=========================================================
"
echo "Quick verification:"
echo "  snow sql -c $CONNECTION -q \"SELECT COUNT(*) FROM SCE_EPM_DB.ATOMIC.CONTRACT;\""
echo "  snow sql -c $CONNECTION -q \"SELECT * FROM SCE_EPM_DB.CONTRACTS.CONTRACT_SUMMARY_V LIMIT 5;\""
