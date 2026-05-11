-- ============================================================================
-- SCE EPM — Cortex Search Service Deployment
-- Two services:
--   (1) CONTRACT_CLAUSE_SEARCH — clause-level RAG (Q2, Q3, Q5, Q6)
--   (2) AMENDMENT_FILE_SEARCH  — search over amendment summaries / filenames (Q1, Q2)
-- ============================================================================

USE DATABASE SCE_EPM_DB;
USE SCHEMA DOCS;

-- ----------------------------------------------------------------------------
-- 1. Promote chunks from ATOMIC.CONTRACT_DOCUMENT_CHUNK into DOCS.CLAUSES
--    (denormalized table optimized for search with a COMBINED_TEXT column)
-- ----------------------------------------------------------------------------
CREATE OR REPLACE TABLE CLAUSES AS
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
    cp.COUNTERPARTY_NAME                                                AS SUPPLIER,
    c.RESOURCE_TYPE,
    c.CAPACITY_MW,
    c.STATUS                                                            AS CONTRACT_STATUS,
    -- Concatenate all searchable fields into a single column.  The leading
    -- section title makes BM25 / vector search latch onto clause topic.
    ck.SECTION_TITLE || '. ' || ck.CONTENT                              AS COMBINED_TEXT,
    ck.CONTENT,
    ck.CREATED_AT
FROM SCE_EPM_DB.ATOMIC.CONTRACT_DOCUMENT_CHUNK  ck
JOIN SCE_EPM_DB.ATOMIC.CONTRACT                  c   USING (CONTRACT_ID)
LEFT JOIN SCE_EPM_DB.ATOMIC.COUNTERPARTY         cp  USING (COUNTERPARTY_ID);

COMMENT ON TABLE CLAUSES IS
'Denormalized contract-clause chunks (base + amendments) for Cortex Search.';

-- ----------------------------------------------------------------------------
-- 2. Cortex Search Service — clause-level
-- ----------------------------------------------------------------------------
CREATE OR REPLACE CORTEX SEARCH SERVICE CONTRACT_CLAUSE_SEARCH
ON COMBINED_TEXT
ATTRIBUTES CONTRACT_ID, AMENDMENT_ID, DOC_TYPE, CLAUSE_TYPE,
           CONTRACT_NAME, SUPPLIER, RESOURCE_TYPE, CAPACITY_MW,
           CONTRACT_STATUS, SECTION_TITLE, PAGE_NUMBER, SOURCE_FILE
WAREHOUSE = SCE_EPM_WH
TARGET_LAG = '1 hour'
AS (
    SELECT
        CHUNK_ID,
        CONTRACT_ID,
        AMENDMENT_ID,
        DOC_TYPE,
        CLAUSE_TYPE,
        SECTION_TITLE,
        PAGE_NUMBER,
        SOURCE_FILE,
        CONTRACT_NAME,
        SUPPLIER,
        RESOURCE_TYPE,
        CAPACITY_MW,
        CONTRACT_STATUS,
        COMBINED_TEXT,
        CONTENT
    FROM SCE_EPM_DB.DOCS.CLAUSES
);
COMMENT ON CORTEX SEARCH SERVICE CONTRACT_CLAUSE_SEARCH IS
'Clause-level semantic search across base contracts and amendments. Filterable by CLAUSE_TYPE (CURTAILMENT, METERING, RA_REMEDY, etc.).';

-- ----------------------------------------------------------------------------
-- 3. Amendment-level search (filename + summary) — supports Q1 / Q2
-- ----------------------------------------------------------------------------
CREATE OR REPLACE TABLE AMENDMENT_INDEX AS
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
    -- Combined searchable text: filename + summary + categories
    'Amendment ' || COALESCE(a.AMENDMENT_NUMBER::STRING, '?') ||
    ' — ' || a.DOC_TYPE || ' — ' ||
    a.FILE_NAME || '. ' || COALESCE(a.SUMMARY, '')             AS COMBINED_TEXT
FROM SCE_EPM_DB.ATOMIC.AMENDMENT  a
JOIN SCE_EPM_DB.ATOMIC.CONTRACT    c  USING (CONTRACT_ID)
LEFT JOIN SCE_EPM_DB.ATOMIC.COUNTERPARTY cp USING (COUNTERPARTY_ID);

COMMENT ON TABLE AMENDMENT_INDEX IS
'Searchable index of contract amendments (filename + summary).';

CREATE OR REPLACE CORTEX SEARCH SERVICE AMENDMENT_FILE_SEARCH
ON COMBINED_TEXT
ATTRIBUTES CONTRACT_ID, AMENDMENT_ID, AMENDMENT_NUMBER, DOC_TYPE,
           CONTRACT_NAME, SUPPLIER, FILE_NAME, EXECUTION_DATE
WAREHOUSE = SCE_EPM_WH
TARGET_LAG = '1 hour'
AS (
    SELECT
        AMENDMENT_ID,
        CONTRACT_ID,
        CONTRACT_NAME,
        SUPPLIER,
        AMENDMENT_NUMBER,
        EXECUTION_DATE,
        DOC_TYPE,
        FILE_NAME,
        STAGE_PATH,
        PAGE_COUNT,
        SUMMARY,
        COMBINED_TEXT
    FROM SCE_EPM_DB.DOCS.AMENDMENT_INDEX
);
COMMENT ON CORTEX SEARCH SERVICE AMENDMENT_FILE_SEARCH IS
'Search across amendment filenames and summaries (Q1 / Q2).';

-- ----------------------------------------------------------------------------
-- 4. Grants
-- ----------------------------------------------------------------------------
GRANT SELECT ON ALL TABLES IN SCHEMA DOCS TO ROLE SCE_EPM_APP_ROLE;
GRANT USAGE  ON CORTEX SEARCH SERVICE CONTRACT_CLAUSE_SEARCH TO ROLE SCE_EPM_APP_ROLE;
GRANT USAGE  ON CORTEX SEARCH SERVICE AMENDMENT_FILE_SEARCH  TO ROLE SCE_EPM_APP_ROLE;

-- ----------------------------------------------------------------------------
-- 5. Verification (commented)
-- ----------------------------------------------------------------------------
-- SELECT * FROM TABLE(SCE_EPM_DB.DOCS.CONTRACT_CLAUSE_SEARCH(
--   QUERY => 'remedy if seller fails to deliver Resource Adequacy capacity',
--   LIMIT => 10
-- ));
--
-- SELECT * FROM TABLE(SCE_EPM_DB.DOCS.AMENDMENT_FILE_SEARCH(
--   QUERY => 'amendments to CTR-001',
--   FILTER => {'@eq': {'CONTRACT_ID': 'CTR-001'}},
--   LIMIT => 10
-- ));
