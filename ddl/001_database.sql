-- ============================================================================
-- SCE EPM Contract Intelligence Chatbot
-- Database, Schemas, Warehouses, Stages, Roles
-- ============================================================================

CREATE DATABASE IF NOT EXISTS SCE_EPM_DB;
USE DATABASE SCE_EPM_DB;

-- ----------------------------------------------------------------------------
-- SCHEMAS
-- ----------------------------------------------------------------------------
CREATE SCHEMA IF NOT EXISTS RAW;
COMMENT ON SCHEMA RAW IS 'Landing zone for contract metadata and document ingestion';

CREATE SCHEMA IF NOT EXISTS ATOMIC;
COMMENT ON SCHEMA ATOMIC IS 'Normalized contract / amendment / clause entities';

CREATE SCHEMA IF NOT EXISTS CONTRACTS;
COMMENT ON SCHEMA CONTRACTS IS 'Analytics views (curtailment, capacity, metering, amendments)';

CREATE SCHEMA IF NOT EXISTS DOCS;
COMMENT ON SCHEMA DOCS IS 'Document chunks for Cortex Search (PDF clauses, amendment text)';

CREATE SCHEMA IF NOT EXISTS CORTEX;
COMMENT ON SCHEMA CORTEX IS 'Semantic models, Cortex Agent definitions, search services';

CREATE SCHEMA IF NOT EXISTS SPCS;
COMMENT ON SCHEMA SPCS IS 'Snowpark Container Services image repo and stages';

-- ----------------------------------------------------------------------------
-- WAREHOUSES
-- ----------------------------------------------------------------------------
CREATE WAREHOUSE IF NOT EXISTS SCE_EPM_WH
    WAREHOUSE_SIZE = 'SMALL'
    AUTO_SUSPEND = 60
    AUTO_RESUME = TRUE
    COMMENT = 'Compute for SCE EPM contract chatbot';

-- ----------------------------------------------------------------------------
-- STAGES
-- ----------------------------------------------------------------------------
USE SCHEMA RAW;

CREATE STAGE IF NOT EXISTS DATA_STAGE
    COMMENT = 'Stage for synthetic parquet/CSV uploads';

CREATE STAGE IF NOT EXISTS PDF_STAGE
    DIRECTORY = (ENABLE = TRUE)
    COMMENT = 'Stage for contract / amendment PDF files';

USE SCHEMA CORTEX;

CREATE STAGE IF NOT EXISTS SEMANTIC_MODELS
    COMMENT = 'Cortex Analyst semantic model YAML files';

-- ----------------------------------------------------------------------------
-- FILE FORMATS
-- ----------------------------------------------------------------------------
USE SCHEMA RAW;

CREATE FILE FORMAT IF NOT EXISTS PARQUET_FORMAT
    TYPE = 'PARQUET' COMPRESSION = 'SNAPPY';

CREATE FILE FORMAT IF NOT EXISTS CSV_FORMAT
    TYPE = 'CSV' FIELD_DELIMITER = ',' SKIP_HEADER = 1
    FIELD_OPTIONALLY_ENCLOSED_BY = '"' NULL_IF = ('NULL', 'null', '');

-- ----------------------------------------------------------------------------
-- ROLE / GRANTS for SPCS app
-- ----------------------------------------------------------------------------
CREATE ROLE IF NOT EXISTS SCE_EPM_APP_ROLE;

GRANT USAGE ON DATABASE SCE_EPM_DB TO ROLE SCE_EPM_APP_ROLE;
GRANT USAGE ON SCHEMA SCE_EPM_DB.RAW       TO ROLE SCE_EPM_APP_ROLE;
GRANT USAGE ON SCHEMA SCE_EPM_DB.ATOMIC    TO ROLE SCE_EPM_APP_ROLE;
GRANT USAGE ON SCHEMA SCE_EPM_DB.CONTRACTS TO ROLE SCE_EPM_APP_ROLE;
GRANT USAGE ON SCHEMA SCE_EPM_DB.DOCS      TO ROLE SCE_EPM_APP_ROLE;
GRANT USAGE ON SCHEMA SCE_EPM_DB.CORTEX    TO ROLE SCE_EPM_APP_ROLE;
GRANT USAGE ON SCHEMA SCE_EPM_DB.SPCS      TO ROLE SCE_EPM_APP_ROLE;
GRANT USAGE ON WAREHOUSE SCE_EPM_WH        TO ROLE SCE_EPM_APP_ROLE;

COMMENT ON DATABASE SCE_EPM_DB IS
'SCE EPM Contract Intelligence — PPA/RA contract & amendment chatbot powered by Snowflake Cortex';
