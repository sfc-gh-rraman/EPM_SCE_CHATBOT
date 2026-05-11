-- ============================================================================
-- SCE EPM — Analytics Views (CONTRACTS schema)
-- Powering the 6 chatbot question categories
-- ============================================================================

USE DATABASE SCE_EPM_DB;
USE SCHEMA CONTRACTS;

-- ----------------------------------------------------------------------------
-- CONTRACT_SUMMARY_V (Q4 — capacity threshold filtering)
-- ----------------------------------------------------------------------------
CREATE OR REPLACE VIEW CONTRACT_SUMMARY_V AS
SELECT
    c.CONTRACT_ID,
    c.CONTRACT_NAME,
    cp.COUNTERPARTY_NAME              AS SUPPLIER,
    c.CONTRACT_TYPE,
    c.RESOURCE_TYPE,
    c.CAPACITY_MW,
    c.EXECUTION_DATE,
    c.TERM_START_DATE,
    c.TERM_END_DATE,
    c.STATUS,
    c.STATUS = 'ACTIVE'               AS IS_ACTIVE,
    c.BASE_PRICE_USD_MWH,
    c.DELIVERY_POINT,
    c.POI_SUBSTATION
FROM SCE_EPM_DB.ATOMIC.CONTRACT c
LEFT JOIN SCE_EPM_DB.ATOMIC.COUNTERPARTY cp USING (COUNTERPARTY_ID);
COMMENT ON VIEW CONTRACT_SUMMARY_V IS
'Tabular contract listing for capacity-threshold and supplier queries (Q4).';

-- ----------------------------------------------------------------------------
-- CONTRACT_CURTAILMENT_V (Q3 — curtailment-term filtering)
-- ----------------------------------------------------------------------------
CREATE OR REPLACE VIEW CONTRACT_CURTAILMENT_V AS
SELECT
    c.CONTRACT_ID,
    c.CONTRACT_NAME,
    cp.COUNTERPARTY_NAME      AS SUPPLIER,
    c.RESOURCE_TYPE,
    c.CAPACITY_MW,
    c.CURTAILMENT_FLAG,
    c.CURTAILMENT_TYPE,
    c.CURTAILMENT_CAP_HRS,
    c.STATUS
FROM SCE_EPM_DB.ATOMIC.CONTRACT c
LEFT JOIN SCE_EPM_DB.ATOMIC.COUNTERPARTY cp USING (COUNTERPARTY_ID)
WHERE c.CURTAILMENT_FLAG = TRUE;
COMMENT ON VIEW CONTRACT_CURTAILMENT_V IS
'Active contracts with curtailment provisions (Q3).';

-- ----------------------------------------------------------------------------
-- AMENDMENT_TIMELINE_V (Q1 — amendment count + first/most recent dates)
-- ----------------------------------------------------------------------------
CREATE OR REPLACE VIEW AMENDMENT_TIMELINE_V AS
SELECT
    c.CONTRACT_ID,
    c.CONTRACT_NAME,
    cp.COUNTERPARTY_NAME            AS SUPPLIER,
    COUNT(a.AMENDMENT_ID)           AS AMENDMENT_COUNT,
    MIN(a.EXECUTION_DATE)           AS FIRST_AMENDMENT_DATE,
    MAX(a.EXECUTION_DATE)           AS MOST_RECENT_AMENDMENT_DATE,
    ARRAY_AGG(a.DOC_TYPE)           WITHIN GROUP (ORDER BY a.AMENDMENT_NUMBER) AS DOC_TYPES,
    ARRAY_AGG(a.SUMMARY)            WITHIN GROUP (ORDER BY a.AMENDMENT_NUMBER) AS AMENDMENT_SUMMARIES
FROM SCE_EPM_DB.ATOMIC.CONTRACT c
LEFT JOIN SCE_EPM_DB.ATOMIC.COUNTERPARTY cp USING (COUNTERPARTY_ID)
LEFT JOIN SCE_EPM_DB.ATOMIC.AMENDMENT  a   ON a.CONTRACT_ID = c.CONTRACT_ID
GROUP BY c.CONTRACT_ID, c.CONTRACT_NAME, cp.COUNTERPARTY_NAME;
COMMENT ON VIEW AMENDMENT_TIMELINE_V IS
'Per-contract amendment counts and date range (Q1).';

-- ----------------------------------------------------------------------------
-- AMENDMENT_DETAIL_V (Q1 / Q2 supporting view)
-- ----------------------------------------------------------------------------
CREATE OR REPLACE VIEW AMENDMENT_DETAIL_V AS
SELECT
    a.AMENDMENT_ID,
    a.CONTRACT_ID,
    c.CONTRACT_NAME,
    a.AMENDMENT_NUMBER,
    a.EXECUTION_DATE,
    a.COUNTERPARTY_NAME,
    a.DOC_TYPE,
    a.FILE_NAME,
    a.STAGE_PATH,
    a.PAGE_COUNT,
    a.SUMMARY,
    a.CHANGE_CATEGORIES
FROM SCE_EPM_DB.ATOMIC.AMENDMENT a
JOIN SCE_EPM_DB.ATOMIC.CONTRACT  c USING (CONTRACT_ID);
COMMENT ON VIEW AMENDMENT_DETAIL_V IS
'Individual amendment records joinable with PDF chunks for Q2.';

-- ----------------------------------------------------------------------------
-- METERING_MISMATCH_V (Q6 — paid by SCE meter but ISO meter exists)
-- ----------------------------------------------------------------------------
CREATE OR REPLACE VIEW METERING_MISMATCH_V AS
SELECT
    c.CONTRACT_ID,
    c.CONTRACT_NAME,
    cp.COUNTERPARTY_NAME      AS SUPPLIER,
    c.CAPACITY_MW,
    m.PAYMENT_METER,
    m.SCE_METER_ID,
    m.ISO_METER_FLAG,
    m.ISO_METER_ID,
    m.MISMATCH_FLAG,
    m.METERING_NOTES
FROM SCE_EPM_DB.ATOMIC.CONTRACT          c
JOIN SCE_EPM_DB.ATOMIC.METERING_CONFIG    m USING (CONTRACT_ID)
LEFT JOIN SCE_EPM_DB.ATOMIC.COUNTERPARTY  cp USING (COUNTERPARTY_ID)
WHERE m.MISMATCH_FLAG = TRUE;
COMMENT ON VIEW METERING_MISMATCH_V IS
'Contracts paid via SCE meter but with separate ISO meter (Q6).';

-- ----------------------------------------------------------------------------
-- EANEP_DEGRADATION_V (Q5 — combine structured w/ concept search)
-- ----------------------------------------------------------------------------
CREATE OR REPLACE VIEW EANEP_DEGRADATION_V AS
SELECT
    c.CONTRACT_ID,
    c.CONTRACT_NAME,
    cp.COUNTERPARTY_NAME      AS SUPPLIER,
    c.CAPACITY_MW,
    c.EANEP_FACTOR,
    c.DEGRADATION_FACTOR,
    c.STATUS
FROM SCE_EPM_DB.ATOMIC.CONTRACT c
LEFT JOIN SCE_EPM_DB.ATOMIC.COUNTERPARTY cp USING (COUNTERPARTY_ID)
WHERE c.EANEP_FACTOR IS NOT NULL OR c.DEGRADATION_FACTOR IS NOT NULL;
COMMENT ON VIEW EANEP_DEGRADATION_V IS
'Contracts with EANEP / degradation factor metadata (Q5).';

-- ----------------------------------------------------------------------------
-- GRANTS
-- ----------------------------------------------------------------------------
GRANT SELECT ON ALL VIEWS    IN SCHEMA CONTRACTS TO ROLE SCE_EPM_APP_ROLE;
GRANT SELECT ON FUTURE VIEWS IN SCHEMA CONTRACTS TO ROLE SCE_EPM_APP_ROLE;
