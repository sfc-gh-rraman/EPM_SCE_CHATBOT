-- =============================================================================
-- SCE EPM Contract Chatbot - SPCS Access Grants
-- =============================================================================
-- Run this script to grant access to the SCE EPM service
-- =============================================================================

USE DATABASE SCE_EPM_DB;
USE SCHEMA SPCS;

-- Grant usage on compute pool
GRANT USAGE ON COMPUTE POOL SCE_EPM_COMPUTE_POOL TO ROLE SCE_EPM_APP_ROLE;

-- Grant usage on image repository
GRANT READ ON IMAGE REPOSITORY SCE_EPM_IMAGES TO ROLE SCE_EPM_APP_ROLE;

-- Grant service access
GRANT USAGE ON SERVICE SCE_EPM_SERVICE TO ROLE SCE_EPM_APP_ROLE;

-- Grant access to database and schemas
GRANT USAGE ON DATABASE SCE_EPM_DB TO ROLE SCE_EPM_APP_ROLE;
GRANT USAGE ON ALL SCHEMAS IN DATABASE SCE_EPM_DB TO ROLE SCE_EPM_APP_ROLE;
GRANT SELECT ON ALL TABLES IN SCHEMA SCE_EPM_DB.ATOMIC    TO ROLE SCE_EPM_APP_ROLE;
GRANT SELECT ON ALL VIEWS  IN SCHEMA SCE_EPM_DB.CONTRACTS TO ROLE SCE_EPM_APP_ROLE;
GRANT SELECT ON ALL TABLES IN SCHEMA SCE_EPM_DB.DOCS      TO ROLE SCE_EPM_APP_ROLE;

-- Grant access to Cortex Search services
GRANT USAGE ON CORTEX SEARCH SERVICE SCE_EPM_DB.DOCS.CONTRACT_CLAUSE_SEARCH TO ROLE SCE_EPM_APP_ROLE;
GRANT USAGE ON CORTEX SEARCH SERVICE SCE_EPM_DB.DOCS.AMENDMENT_FILE_SEARCH  TO ROLE SCE_EPM_APP_ROLE;

-- Grant warehouse usage
GRANT USAGE ON WAREHOUSE SCE_EPM_WH TO ROLE SCE_EPM_APP_ROLE;

-- Output
SELECT 'Access grants complete for SCE_EPM_APP_ROLE' as STATUS;
