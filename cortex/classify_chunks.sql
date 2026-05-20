-- ============================================================================
-- Apply CLAUSE_TYPE labels using regex heuristics first, AI_CLASSIFY fallback
-- ============================================================================
USE DATABASE SCE_EPM_DB;
USE WAREHOUSE SCE_EPM_WH;

-- ----------------------------------------------------------------------------
-- 1. Heuristic regex pass — fast and free, catches majority of clauses
-- ----------------------------------------------------------------------------
UPDATE ATOMIC.CONTRACT_DOCUMENT_CHUNK
SET CLAUSE_TYPE =
    CASE
        WHEN REGEXP_LIKE(CONTENT, '\\b(curtail|curtailment|curtailing|curtailed)\\b', 'i')
            THEN 'CURTAILMENT'
        WHEN REGEXP_LIKE(CONTENT, '\\b(resource adequacy|RA capacity|RA showing|substitute capacity|replacement RA|RA remedy)\\b', 'i')
            THEN 'RA_REMEDY'
        WHEN REGEXP_LIKE(CONTENT, '\\b(meter|metering|revenue meter|CAISO meter|PMI|telemetry)\\b', 'i')
            THEN 'METERING'
        WHEN REGEXP_LIKE(CONTENT, '\\b(EANEP|expected (annual )?net energy production|guaranteed energy|production guarantee|capacity factor)\\b', 'i')
            THEN 'EANEP'
        WHEN REGEXP_LIKE(CONTENT, '\\b(degradation|module degradation|degradation factor|annual degradation)\\b', 'i')
            THEN 'DEGRADATION'
        WHEN REGEXP_LIKE(CONTENT, '\\b(deliver|delivery failure|failure to deliver|product deficiency|liquidated damages|cure period)\\b', 'i')
            THEN 'DELIVERY_FAILURE'
        WHEN REGEXP_LIKE(CONTENT, '\\b(price|pricing|contract price|escalator|capacity payment|\\$\\s*/\\s*MWh|kW-month)\\b', 'i')
            THEN 'PRICING'
        WHEN REGEXP_LIKE(CONTENT, '\\b(termination|terminate|early termination|default and termination)\\b', 'i')
            THEN 'TERMINATION'
        WHEN REGEXP_LIKE(CONTENT, '\\b(initial term|contract term|term of (this )?agreement|commercial operation date|COD)\\b', 'i')
            THEN 'TERM'
        ELSE 'GENERAL'
    END;

SELECT CLAUSE_TYPE, COUNT(*) AS n
FROM ATOMIC.CONTRACT_DOCUMENT_CHUNK
GROUP BY 1 ORDER BY 2 DESC;
