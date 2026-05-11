-- ============================================================================
-- SCE EPM — Custom Tools (SQL stored procedures used as Cortex Agent tools)
-- ============================================================================
--
-- Three custom tools that complement Cortex Analyst + Cortex Search:
--   1. PARSE_AMENDMENT_FILENAME — parse a filename into structured fields
--   2. GET_CONTRACT_360         — full dossier for a contract
--   3. COMPARE_CLAUSE_ACROSS_CONTRACTS
--                               — concept extraction across the portfolio (Q5)
-- ============================================================================

USE DATABASE SCE_EPM_DB;
USE SCHEMA CORTEX;

-- ----------------------------------------------------------------------------
-- 1. PARSE_AMENDMENT_FILENAME
--     Parses {CONTRACT_ID}_{YYYY-MM-DD}_{COUNTERPARTY}_{FREE_TEXT_DOC_TYPE}.pdf
--     Returns structured JSON.
-- ----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION PARSE_AMENDMENT_FILENAME(FILE_NAME STRING)
RETURNS OBJECT
LANGUAGE SQL
AS
$$
    OBJECT_CONSTRUCT(
        'file_name',         FILE_NAME,
        'contract_id',       SPLIT_PART(FILE_NAME, '_', 1),
        'execution_date',    TRY_TO_DATE(SPLIT_PART(FILE_NAME, '_', 2)),
        'counterparty_token', SPLIT_PART(FILE_NAME, '_', 3),
        'doc_type_raw',      REGEXP_REPLACE(
                                 SPLIT_PART(REGEXP_REPLACE(FILE_NAME, '\\.pdf$', '', 1, 0, 'i'), '_', 4),
                                 '_+', ' '
                             ),
        'doc_type',
            CASE
              WHEN LOWER(FILE_NAME) LIKE '%amend%'      THEN 'AMENDMENT'
              WHEN LOWER(FILE_NAME) LIKE '%restat%'     THEN 'RESTATEMENT'
              WHEN LOWER(FILE_NAME) LIKE '%side%'       THEN 'SIDE_LETTER'
              WHEN LOWER(FILE_NAME) LIKE '%notice%'     THEN 'NOTICE'
              ELSE 'UNKNOWN'
            END
    )
$$;
COMMENT ON FUNCTION PARSE_AMENDMENT_FILENAME(STRING) IS
'Parse an amendment filename of the form {CONTRACT_ID}_{YYYY-MM-DD}_{COUNTERPARTY}_{DOC_TYPE}.pdf into structured fields.';


-- ----------------------------------------------------------------------------
-- 2. GET_CONTRACT_360
--     Returns a single JSON object with everything we know about a contract:
--       master row + supplier + amendments + metering + clause-type counts.
-- ----------------------------------------------------------------------------
CREATE OR REPLACE PROCEDURE GET_CONTRACT_360(CONTRACT_ID STRING)
RETURNS OBJECT
LANGUAGE SQL
AS
$$
BEGIN
    LET res OBJECT := (SELECT OBJECT_CONSTRUCT(
        'contract',     (SELECT OBJECT_CONSTRUCT(
                            'contract_id', c.CONTRACT_ID, 'contract_name', c.CONTRACT_NAME,
                            'supplier', cp.COUNTERPARTY_NAME, 'contract_type', c.CONTRACT_TYPE,
                            'resource_type', c.RESOURCE_TYPE, 'capacity_mw', c.CAPACITY_MW,
                            'execution_date', c.EXECUTION_DATE, 'term_start_date', c.TERM_START_DATE,
                            'term_end_date', c.TERM_END_DATE, 'status', c.STATUS,
                            'curtailment_flag', c.CURTAILMENT_FLAG, 'curtailment_type', c.CURTAILMENT_TYPE,
                            'curtailment_cap_hrs', c.CURTAILMENT_CAP_HRS,
                            'eanep_factor', c.EANEP_FACTOR, 'degradation_factor', c.DEGRADATION_FACTOR,
                            'base_price_usd_mwh', c.BASE_PRICE_USD_MWH,
                            'delivery_point', c.DELIVERY_POINT, 'poi_substation', c.POI_SUBSTATION)
                         FROM SCE_EPM_DB.ATOMIC.CONTRACT c
                         LEFT JOIN SCE_EPM_DB.ATOMIC.COUNTERPARTY cp USING (COUNTERPARTY_ID)
                         WHERE c.CONTRACT_ID = :CONTRACT_ID),
        'amendments',   (SELECT ARRAY_AGG(OBJECT_CONSTRUCT(
                            'amendment_number', AMENDMENT_NUMBER, 'execution_date', EXECUTION_DATE,
                            'doc_type', DOC_TYPE, 'file_name', FILE_NAME,
                            'page_count', PAGE_COUNT, 'summary', SUMMARY,
                            'change_categories', CHANGE_CATEGORIES))
                          WITHIN GROUP (ORDER BY AMENDMENT_NUMBER)
                         FROM SCE_EPM_DB.ATOMIC.AMENDMENT WHERE CONTRACT_ID = :CONTRACT_ID),
        'metering',     (SELECT OBJECT_CONSTRUCT(
                            'payment_meter', PAYMENT_METER, 'sce_meter_id', SCE_METER_ID,
                            'iso_meter_flag', ISO_METER_FLAG, 'iso_meter_id', ISO_METER_ID,
                            'mismatch_flag', MISMATCH_FLAG, 'metering_notes', METERING_NOTES)
                         FROM SCE_EPM_DB.ATOMIC.METERING_CONFIG WHERE CONTRACT_ID = :CONTRACT_ID),
        'clause_index', (SELECT OBJECT_AGG(CLAUSE_TYPE, CHUNK_COUNT::VARIANT)
                         FROM (SELECT CLAUSE_TYPE, COUNT(*) AS CHUNK_COUNT
                               FROM SCE_EPM_DB.ATOMIC.CONTRACT_DOCUMENT_CHUNK
                               WHERE CONTRACT_ID = :CONTRACT_ID GROUP BY CLAUSE_TYPE))
    ));
    RETURN res;
END;
$$;
COMMENT ON PROCEDURE GET_CONTRACT_360(STRING) IS
'Return a 360-degree dossier (master + amendments + metering + clause-type counts) for a single contract.';


-- ----------------------------------------------------------------------------
-- 3. COMPARE_CLAUSE_ACROSS_CONTRACTS  (Q5 — concept extraction)
--     Given a clause type and an optional natural-language concept, returns a
--     ranked list of representative clauses across the portfolio so the agent
--     can group distinct approaches.
-- ----------------------------------------------------------------------------
CREATE OR REPLACE PROCEDURE COMPARE_CLAUSE_ACROSS_CONTRACTS(
    CLAUSE_TYPE  STRING,
    CONCEPT      STRING DEFAULT NULL,
    MAX_RESULTS  NUMBER DEFAULT 12
)
RETURNS ARRAY
LANGUAGE SQL
AS
$$
DECLARE
    out_arr    ARRAY;
    search_json STRING;
BEGIN
    IF (CONCEPT IS NOT NULL AND LENGTH(TRIM(CONCEPT)) > 0) THEN
        LET search_payload STRING := '{"query":"' || REPLACE(:CONCEPT, '"', '\\"') ||
            '","filter":{"@eq":{"CLAUSE_TYPE":"' || :CLAUSE_TYPE ||
            '"}},"limit":' || :MAX_RESULTS::STRING ||
            ',"columns":["CONTRACT_ID","CONTRACT_NAME","SUPPLIER","AMENDMENT_ID","DOC_TYPE","CLAUSE_TYPE","SECTION_TITLE","PAGE_NUMBER","CONTENT","SOURCE_FILE"]}';
        LET rs RESULTSET := (
            EXECUTE IMMEDIATE
                'SELECT GET(PARSE_JSON(SNOWFLAKE.CORTEX.SEARCH_PREVIEW(''SCE_EPM_DB.DOCS.CONTRACT_CLAUSE_SEARCH'', ''' ||
                REPLACE(:search_payload, '''', '''''') || ''')), ''results'')::ARRAY AS ARR'
        );
        LET c CURSOR FOR rs;
        OPEN c;
        FETCH c INTO out_arr;
        CLOSE c;
    ELSE
        LET rs2 RESULTSET := (
            SELECT ARRAY_AGG(
                OBJECT_CONSTRUCT(
                    'CONTRACT_ID',   CONTRACT_ID,
                    'CONTRACT_NAME', CONTRACT_NAME,
                    'SUPPLIER',      SUPPLIER,
                    'AMENDMENT_ID',  AMENDMENT_ID,
                    'DOC_TYPE',      DOC_TYPE,
                    'CLAUSE_TYPE',   CLAUSE_TYPE,
                    'SECTION_TITLE', SECTION_TITLE,
                    'PAGE_NUMBER',   PAGE_NUMBER,
                    'CONTENT',       CONTENT,
                    'SOURCE_FILE',   SOURCE_FILE
                )
            ) AS ARR
            FROM (
                SELECT
                    ck.CONTRACT_ID, c.CONTRACT_NAME, cp.COUNTERPARTY_NAME AS SUPPLIER,
                    ck.AMENDMENT_ID, ck.DOC_TYPE, ck.CLAUSE_TYPE,
                    ck.SECTION_TITLE, ck.PAGE_NUMBER, ck.CONTENT, ck.SOURCE_FILE
                FROM (
                    SELECT *,
                           ROW_NUMBER() OVER (PARTITION BY CONTRACT_ID ORDER BY PAGE_NUMBER) AS rn
                    FROM SCE_EPM_DB.ATOMIC.CONTRACT_DOCUMENT_CHUNK
                    WHERE CLAUSE_TYPE = :CLAUSE_TYPE
                ) ck
                JOIN      SCE_EPM_DB.ATOMIC.CONTRACT     c  ON c.CONTRACT_ID    = ck.CONTRACT_ID
                LEFT JOIN SCE_EPM_DB.ATOMIC.COUNTERPARTY cp ON cp.COUNTERPARTY_ID = c.COUNTERPARTY_ID
                WHERE ck.rn = 1
                ORDER BY ck.CONTRACT_ID
                LIMIT :MAX_RESULTS
            )
        );
        LET c2 CURSOR FOR rs2;
        OPEN c2;
        FETCH c2 INTO out_arr;
        CLOSE c2;
    END IF;
    RETURN COALESCE(out_arr, ARRAY_CONSTRUCT());
END;
$$;
COMMENT ON PROCEDURE COMPARE_CLAUSE_ACROSS_CONTRACTS(STRING, STRING, NUMBER) IS
'For a given CLAUSE_TYPE (e.g. RA_REMEDY, METERING, EANEP), return representative clause excerpts across contracts so the agent can group distinct legal approaches. Optional CONCEPT argument routes through Cortex Search.';


-- ----------------------------------------------------------------------------
-- Smoke tests (commented)
-- ----------------------------------------------------------------------------
-- SELECT PARSE_AMENDMENT_FILENAME('CTR-001_2022-09-13_Mojave_First_Amendment.pdf');
-- CALL GET_CONTRACT_360('CTR-001');
-- CALL COMPARE_CLAUSE_ACROSS_CONTRACTS('RA_REMEDY', 'remedy when seller fails to deliver RA capacity', 8);

GRANT USAGE ON FUNCTION  SCE_EPM_DB.CORTEX.PARSE_AMENDMENT_FILENAME(STRING)              TO ROLE SCE_EPM_APP_ROLE;
GRANT USAGE ON PROCEDURE SCE_EPM_DB.CORTEX.GET_CONTRACT_360(STRING)                       TO ROLE SCE_EPM_APP_ROLE;
GRANT USAGE ON PROCEDURE SCE_EPM_DB.CORTEX.COMPARE_CLAUSE_ACROSS_CONTRACTS(STRING, STRING, NUMBER) TO ROLE SCE_EPM_APP_ROLE;
