-- ============================================================================
-- SCE EPM — ATOMIC tables (normalized contract entities)
-- ============================================================================

USE DATABASE SCE_EPM_DB;
USE SCHEMA ATOMIC;

-- ----------------------------------------------------------------------------
-- COUNTERPARTY (suppliers / off-takers)
-- ----------------------------------------------------------------------------
CREATE OR REPLACE TABLE COUNTERPARTY (
    COUNTERPARTY_ID    VARCHAR(50)  PRIMARY KEY,
    COUNTERPARTY_NAME  VARCHAR(200) NOT NULL,
    COUNTERPARTY_TYPE  VARCHAR(50),  -- DEVELOPER | UTILITY | TRADER | IPP
    HQ_STATE           VARCHAR(20),
    CREATED_AT         TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP()
);
COMMENT ON TABLE COUNTERPARTY IS 'Contract counterparties (developers, IPPs, traders).';

-- ----------------------------------------------------------------------------
-- CONTRACT (PPA / RA / Tolling agreements)
-- ----------------------------------------------------------------------------
CREATE OR REPLACE TABLE CONTRACT (
    CONTRACT_ID         VARCHAR(50)  PRIMARY KEY,
    CONTRACT_NAME       VARCHAR(300),
    COUNTERPARTY_ID     VARCHAR(50)  REFERENCES COUNTERPARTY(COUNTERPARTY_ID),
    CONTRACT_TYPE       VARCHAR(40),   -- PPA | RA | TOLLING | HYBRID
    RESOURCE_TYPE       VARCHAR(40),   -- SOLAR | WIND | BATTERY | GAS | HYBRID_SOLAR_BESS
    CAPACITY_MW         FLOAT,         -- Nameplate capacity (MW)
    EXECUTION_DATE      DATE,
    TERM_START_DATE     DATE,
    TERM_END_DATE       DATE,
    STATUS              VARCHAR(30),   -- ACTIVE | EXPIRED | TERMINATED | PROPOSED
    CURTAILMENT_FLAG    BOOLEAN,
    CURTAILMENT_TYPE    VARCHAR(60),   -- ECONOMIC | RELIABILITY | NONE | UNLIMITED_OPERATIONAL
    CURTAILMENT_CAP_HRS NUMBER,        -- Annual curtailment cap (hrs)
    PAYMENT_METER       VARCHAR(20),   -- SCE | ISO | THIRD_PARTY
    ISO_METER_FLAG      BOOLEAN,       -- Has separate CAISO meter
    EANEP_FACTOR        FLOAT,         -- Expected Annual Net Energy Production factor
    DEGRADATION_FACTOR  FLOAT,         -- Annual degradation %
    DELIVERY_POINT      VARCHAR(100),
    POI_SUBSTATION      VARCHAR(100),
    BASE_PRICE_USD_MWH  FLOAT,
    CREATED_AT          TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP()
);
COMMENT ON TABLE CONTRACT IS 'Master contract record (PPA/RA/Tolling).';
COMMENT ON COLUMN CONTRACT.CURTAILMENT_FLAG  IS 'Whether contract permits curtailment by SCE.';
COMMENT ON COLUMN CONTRACT.CURTAILMENT_TYPE  IS 'Type of curtailment permitted.';
COMMENT ON COLUMN CONTRACT.PAYMENT_METER     IS 'Meter used by SCE for settlement.';
COMMENT ON COLUMN CONTRACT.ISO_METER_FLAG    IS 'TRUE if a separate CAISO meter is installed (relevant for Q6).';

-- ----------------------------------------------------------------------------
-- AMENDMENT — derived from filename parsing per requirements
-- ----------------------------------------------------------------------------
CREATE OR REPLACE TABLE AMENDMENT (
    AMENDMENT_ID         VARCHAR(50) PRIMARY KEY,
    CONTRACT_ID          VARCHAR(50) REFERENCES CONTRACT(CONTRACT_ID),
    AMENDMENT_NUMBER     INT,                -- 1, 2, 3, ...
    EXECUTION_DATE       DATE,               -- parsed from filename
    COUNTERPARTY_NAME    VARCHAR(200),       -- parsed from filename
    DOC_TYPE             VARCHAR(60),        -- AMENDMENT | RESTATEMENT | SIDE_LETTER | NOTICE
    FILE_NAME            VARCHAR(500),       -- Original filename in stage
    STAGE_PATH           VARCHAR(1000),      -- @SCE_EPM_DB.RAW.PDF_STAGE/...
    PAGE_COUNT           INT,
    SUMMARY              VARCHAR(4000),      -- One-paragraph human/AI summary
    CHANGE_CATEGORIES    ARRAY,              -- e.g. ['CAPACITY','CURTAILMENT','PRICING']
    CREATED_AT           TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP()
);
COMMENT ON TABLE AMENDMENT IS 'Contract amendments parsed from PDF filenames (Q1).';
COMMENT ON COLUMN AMENDMENT.DOC_TYPE IS 'Document category derived from filename free-text token.';

-- ----------------------------------------------------------------------------
-- CONTRACT_DOCUMENT_CHUNK — chunked PDF text for Cortex Search
-- ----------------------------------------------------------------------------
CREATE OR REPLACE TABLE CONTRACT_DOCUMENT_CHUNK (
    CHUNK_ID         VARCHAR(50) PRIMARY KEY,
    CONTRACT_ID      VARCHAR(50) REFERENCES CONTRACT(CONTRACT_ID),
    AMENDMENT_ID     VARCHAR(50),            -- nullable: NULL for base contract chunks
    DOC_TYPE         VARCHAR(60),            -- BASE_CONTRACT | AMENDMENT | RESTATEMENT
    SECTION_TITLE    VARCHAR(500),
    CLAUSE_TYPE      VARCHAR(60),            -- CURTAILMENT | DELIVERY_FAILURE | RA_REMEDY |
                                             -- METERING | EANEP | DEGRADATION | PRICING |
                                             -- TERM | TERMINATION | GENERAL
    PAGE_NUMBER      INT,
    CONTENT          TEXT,                   -- Cleaned chunk text
    SOURCE_FILE      VARCHAR(500),
    CREATED_AT       TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP()
);
COMMENT ON TABLE CONTRACT_DOCUMENT_CHUNK IS
'Chunked PDF clauses for Cortex Search. CLAUSE_TYPE supports filtering by concept (Q2/Q3/Q5/Q6).';

-- ----------------------------------------------------------------------------
-- METERING_CONFIG — separate metering detail per contract
-- ----------------------------------------------------------------------------
CREATE OR REPLACE TABLE METERING_CONFIG (
    CONTRACT_ID         VARCHAR(50) PRIMARY KEY REFERENCES CONTRACT(CONTRACT_ID),
    PAYMENT_METER       VARCHAR(20),    -- SCE | ISO | THIRD_PARTY
    SETTLEMENT_METER_ID VARCHAR(80),
    ISO_METER_FLAG      BOOLEAN,
    ISO_METER_ID        VARCHAR(80),
    SCE_METER_ID        VARCHAR(80),
    METERING_NOTES      VARCHAR(1000),
    MISMATCH_FLAG       BOOLEAN          -- TRUE when paid by SCE meter but ISO meter present (Q6)
);
COMMENT ON TABLE METERING_CONFIG IS 'Metering configuration; MISMATCH_FLAG identifies Q6 contracts.';

-- ----------------------------------------------------------------------------
-- GRANTS for app role
-- ----------------------------------------------------------------------------
GRANT SELECT ON ALL TABLES   IN SCHEMA ATOMIC TO ROLE SCE_EPM_APP_ROLE;
GRANT SELECT ON FUTURE TABLES IN SCHEMA ATOMIC TO ROLE SCE_EPM_APP_ROLE;
