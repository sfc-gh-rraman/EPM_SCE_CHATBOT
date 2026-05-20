-- ============================================================================
-- Refresh DOCS denormalized tables → Cortex Search auto-rebuilds via TARGET_LAG
-- ============================================================================
USE DATABASE SCE_EPM_DB;
USE WAREHOUSE SCE_EPM_WH;

-- ----------------------------------------------------------------------------
-- 1. CLAUSES: rebuild from chunk + contract metadata
-- ----------------------------------------------------------------------------
CREATE OR REPLACE TABLE DOCS.CLAUSES AS
SELECT
    ck.CHUNK_ID,
    ck.CONTRACT_ID,
    ck.AMENDMENT_ID,
    ck.DOC_TYPE,
    ck.CLAUSE_TYPE,
    ck.SECTION_TITLE,
    ck.PAGE_NUMBER,
    ck.SOURCE_FILE,
    c.CONTRACT_NAME,
    cp.COUNTERPARTY_NAME                          AS SUPPLIER,
    c.RESOURCE_TYPE,
    c.CAPACITY_MW,
    c.STATUS                                      AS CONTRACT_STATUS,
    SUBSTR(ck.SECTION_TITLE || '. ' || ck.CONTENT, 1, 4000) AS COMBINED_TEXT,
    ck.CONTENT,
    CURRENT_TIMESTAMP()                           AS CREATED_AT
FROM ATOMIC.CONTRACT_DOCUMENT_CHUNK ck
LEFT JOIN ATOMIC.CONTRACT          c   ON c.CONTRACT_ID    = ck.CONTRACT_ID
LEFT JOIN ATOMIC.COUNTERPARTY       cp ON cp.COUNTERPARTY_ID = c.COUNTERPARTY_ID;

-- ----------------------------------------------------------------------------
-- 2. AMENDMENT_INDEX: rebuild
-- ----------------------------------------------------------------------------
CREATE OR REPLACE TABLE DOCS.AMENDMENT_INDEX AS
SELECT
    a.AMENDMENT_ID,
    a.CONTRACT_ID,
    c.CONTRACT_NAME,
    cp.COUNTERPARTY_NAME                                       AS SUPPLIER,
    a.AMENDMENT_NUMBER,
    a.EXECUTION_DATE,
    a.DOC_TYPE,
    a.FILE_NAME,
    a.STAGE_PATH,
    a.PAGE_COUNT,
    a.SUMMARY,
    a.CHANGE_CATEGORIES,
    'Amendment ' || COALESCE(a.AMENDMENT_NUMBER::STRING, '?') ||
    ' — ' || a.DOC_TYPE || ' — ' || a.FILE_NAME ||
    '. ' || COALESCE(a.SUMMARY, '')                            AS COMBINED_TEXT
FROM ATOMIC.AMENDMENT  a
JOIN ATOMIC.CONTRACT    c USING (CONTRACT_ID)
LEFT JOIN ATOMIC.COUNTERPARTY cp USING (COUNTERPARTY_ID);

-- ----------------------------------------------------------------------------
-- 3. Recreate Cortex Search services so they pick up the new schema/data
-- ----------------------------------------------------------------------------
CREATE OR REPLACE CORTEX SEARCH SERVICE DOCS.CONTRACT_CLAUSE_SEARCH
ON COMBINED_TEXT
ATTRIBUTES CONTRACT_ID, AMENDMENT_ID, DOC_TYPE, CLAUSE_TYPE,
           CONTRACT_NAME, SUPPLIER, RESOURCE_TYPE, CAPACITY_MW,
           CONTRACT_STATUS, SECTION_TITLE, PAGE_NUMBER, SOURCE_FILE
WAREHOUSE = SCE_EPM_WH
TARGET_LAG = '1 hour'
AS (
    SELECT CHUNK_ID, CONTRACT_ID, AMENDMENT_ID, DOC_TYPE, CLAUSE_TYPE,
           SECTION_TITLE, PAGE_NUMBER, SOURCE_FILE, CONTRACT_NAME, SUPPLIER,
           RESOURCE_TYPE, CAPACITY_MW, CONTRACT_STATUS, COMBINED_TEXT, CONTENT
    FROM DOCS.CLAUSES
);

CREATE OR REPLACE CORTEX SEARCH SERVICE DOCS.AMENDMENT_FILE_SEARCH
ON COMBINED_TEXT
ATTRIBUTES CONTRACT_ID, AMENDMENT_ID, AMENDMENT_NUMBER, DOC_TYPE,
           CONTRACT_NAME, SUPPLIER, FILE_NAME, EXECUTION_DATE
WAREHOUSE = SCE_EPM_WH
TARGET_LAG = '1 hour'
AS (
    SELECT AMENDMENT_ID, CONTRACT_ID, CONTRACT_NAME, SUPPLIER,
           AMENDMENT_NUMBER, EXECUTION_DATE, DOC_TYPE, FILE_NAME, STAGE_PATH,
           PAGE_COUNT, SUMMARY, COMBINED_TEXT
    FROM DOCS.AMENDMENT_INDEX
);

GRANT USAGE ON CORTEX SEARCH SERVICE DOCS.CONTRACT_CLAUSE_SEARCH TO ROLE SCE_EPM_APP_ROLE;
GRANT USAGE ON CORTEX SEARCH SERVICE DOCS.AMENDMENT_FILE_SEARCH  TO ROLE SCE_EPM_APP_ROLE;

SELECT 'CLAUSES' AS tbl, COUNT(*) FROM DOCS.CLAUSES
UNION ALL SELECT 'AMENDMENT_INDEX', COUNT(*) FROM DOCS.AMENDMENT_INDEX;
