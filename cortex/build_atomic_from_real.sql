-- ============================================================================
-- Build ATOMIC entities from real CPUC corpus
-- ============================================================================
USE DATABASE SCE_EPM_DB;
USE WAREHOUSE SCE_EPM_WH;

-- ----------------------------------------------------------------------------
-- 1. COUNTERPARTY  (one row per distinct cleaned counterparty name)
-- ----------------------------------------------------------------------------
INSERT INTO ATOMIC.COUNTERPARTY (COUNTERPARTY_ID, COUNTERPARTY_NAME, COUNTERPARTY_TYPE, HQ_STATE)
SELECT
    'CP-' || LPAD(ROW_NUMBER() OVER (ORDER BY COUNTERPARTY)::STRING, 4, '0') AS COUNTERPARTY_ID,
    COUNTERPARTY                                AS COUNTERPARTY_NAME,
    'DEVELOPER'                                 AS COUNTERPARTY_TYPE,
    'CA'                                        AS HQ_STATE
FROM (
    SELECT DISTINCT
        COALESCE(NULLIF(TRIM(COUNTERPARTY), ''), 'Unknown ' || PROJECT_ID) AS COUNTERPARTY
    FROM RAW.PDF_INVENTORY
    WHERE COUNTERPARTY IS NOT NULL
);

-- ----------------------------------------------------------------------------
-- 2. CONTRACT  (one row per project_id; PPAs only)
--      Coalesce project_id when missing using PARSE_AMENDMENT-like fallback
-- ----------------------------------------------------------------------------
INSERT INTO ATOMIC.CONTRACT (
    CONTRACT_ID, CONTRACT_NAME, COUNTERPARTY_ID, CONTRACT_TYPE, RESOURCE_TYPE,
    CAPACITY_MW, EXECUTION_DATE, TERM_START_DATE, TERM_END_DATE, STATUS,
    CURTAILMENT_FLAG, CURTAILMENT_TYPE, CURTAILMENT_CAP_HRS,
    PAYMENT_METER, ISO_METER_FLAG, EANEP_FACTOR, DEGRADATION_FACTOR,
    DELIVERY_POINT, POI_SUBSTATION, BASE_PRICE_USD_MWH
)
WITH base AS (
    SELECT
        COALESCE('CTR-' || PROJECT_ID, 'CTR-NA-' || ROW_NUMBER() OVER (ORDER BY NORMALIZED_FILENAME)) AS CONTRACT_ID,
        COUNTERPARTY,
        EXEC_DATE,
        DOC_TYPE,
        ROW_NUMBER() OVER (PARTITION BY PROJECT_ID, COUNTERPARTY
                           ORDER BY CASE WHEN DOC_TYPE='PPA' THEN 0 ELSE 1 END,
                                    EXEC_DATE NULLS LAST) AS rn
    FROM RAW.PDF_INVENTORY
    WHERE PROJECT_ID IS NOT NULL
)
SELECT
    b.CONTRACT_ID,
    b.COUNTERPARTY                            AS CONTRACT_NAME,
    cp.COUNTERPARTY_ID,
    'PPA'                                     AS CONTRACT_TYPE,
    'UNKNOWN'                                 AS RESOURCE_TYPE,
    NULL                                      AS CAPACITY_MW,
    b.EXEC_DATE                               AS EXECUTION_DATE,
    NULL, NULL, 'ACTIVE',
    NULL, NULL, NULL,
    NULL, NULL, NULL, NULL,
    NULL, NULL, NULL
FROM base b
LEFT JOIN ATOMIC.COUNTERPARTY cp ON cp.COUNTERPARTY_NAME = b.COUNTERPARTY
WHERE b.rn = 1;

-- ----------------------------------------------------------------------------
-- 3. AMENDMENT  (every non-PPA / non-AGREEMENT file is a 'document' record)
-- ----------------------------------------------------------------------------
INSERT INTO ATOMIC.AMENDMENT (
    AMENDMENT_ID, CONTRACT_ID, AMENDMENT_NUMBER, EXECUTION_DATE,
    COUNTERPARTY_NAME, DOC_TYPE, FILE_NAME, STAGE_PATH, PAGE_COUNT,
    SUMMARY, CHANGE_CATEGORIES
)
SELECT
    'AMD-' || LPAD(ROW_NUMBER() OVER (ORDER BY PROJECT_ID, EXEC_DATE NULLS LAST)::STRING, 5, '0'),
    'CTR-' || PROJECT_ID,
    ROW_NUMBER() OVER (PARTITION BY PROJECT_ID ORDER BY EXEC_DATE NULLS LAST, NORMALIZED_FILENAME),
    EXEC_DATE,
    COUNTERPARTY,
    DOC_TYPE,
    FILENAME,
    '@SCE_EPM_DB.RAW.PDF_STAGE/' || NORMALIZED_FILENAME,
    NULL,
    NULL,
    NULL
FROM RAW.PDF_INVENTORY
WHERE PROJECT_ID IS NOT NULL
  AND DOC_TYPE NOT IN ('PPA');  -- amendments / restatements / side letters / notices / etc.

-- ----------------------------------------------------------------------------
-- 4. CONTRACT_DOCUMENT_CHUNK  using Cortex SPLIT_TEXT_RECURSIVE_CHARACTER
--      ~1800 chars with 200 overlap. Returns LATERAL TABLE of chunks.
-- ----------------------------------------------------------------------------
INSERT INTO ATOMIC.CONTRACT_DOCUMENT_CHUNK (
    CHUNK_ID, CONTRACT_ID, AMENDMENT_ID, DOC_TYPE,
    SECTION_TITLE, CLAUSE_TYPE, PAGE_NUMBER, CONTENT, SOURCE_FILE
)
WITH joined AS (
    SELECT
        pt.NORMALIZED_FILENAME,
        pt.CONTENT                            AS full_text,
        inv.PROJECT_ID,
        inv.DOC_TYPE                          AS file_doc_type,
        'CTR-' || inv.PROJECT_ID              AS contract_id,
        inv.FILENAME                          AS source_file
    FROM RAW.PDF_TEXT       pt
    JOIN RAW.PDF_INVENTORY  inv ON inv.NORMALIZED_FILENAME = pt.NORMALIZED_FILENAME
    WHERE pt.PARSE_STATUS = 'OK'
      AND pt.CONTENT IS NOT NULL
      AND LENGTH(pt.CONTENT) > 100
      AND inv.PROJECT_ID IS NOT NULL
), chunked AS (
    SELECT
        j.NORMALIZED_FILENAME,
        j.contract_id,
        j.file_doc_type,
        j.source_file,
        c.index                               AS chunk_idx,
        c.value::STRING                       AS chunk_text
    FROM joined j,
         LATERAL FLATTEN(input => SNOWFLAKE.CORTEX.SPLIT_TEXT_RECURSIVE_CHARACTER(
             j.full_text, 'none', 1800, 200
         )) c
)
SELECT
    'CHK-' || MD5(NORMALIZED_FILENAME || '_' || chunk_idx)::STRING        AS CHUNK_ID,
    contract_id                                                            AS CONTRACT_ID,
    -- match the AMENDMENT we created above for non-PPA docs
    CASE WHEN file_doc_type <> 'PPA' THEN
        (SELECT a.AMENDMENT_ID
         FROM ATOMIC.AMENDMENT a
         WHERE a.STAGE_PATH = '@SCE_EPM_DB.RAW.PDF_STAGE/' || NORMALIZED_FILENAME
         LIMIT 1)
    END                                                                    AS AMENDMENT_ID,
    CASE WHEN file_doc_type IN ('PPA', 'AGREEMENT') THEN 'BASE_CONTRACT' ELSE file_doc_type END AS DOC_TYPE,
    SUBSTR(chunk_text, 1, 200)                                             AS SECTION_TITLE,
    'GENERAL'                                                              AS CLAUSE_TYPE,  -- temp; AI_CLASSIFY in next step
    chunk_idx                                                              AS PAGE_NUMBER,
    chunk_text                                                             AS CONTENT,
    source_file                                                            AS SOURCE_FILE
FROM chunked;

SELECT 'COUNTERPARTY' AS tbl, COUNT(*) AS rows FROM ATOMIC.COUNTERPARTY
UNION ALL SELECT 'CONTRACT',                COUNT(*) FROM ATOMIC.CONTRACT
UNION ALL SELECT 'AMENDMENT',               COUNT(*) FROM ATOMIC.AMENDMENT
UNION ALL SELECT 'CONTRACT_DOCUMENT_CHUNK', COUNT(*) FROM ATOMIC.CONTRACT_DOCUMENT_CHUNK;
