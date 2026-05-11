"""
SCE EPM Contract Chatbot — Synthetic Data Generator
====================================================

Generates realistic synthetic data for the SCE contract intelligence chatbot:
- 25 PPA / RA / Tolling contracts
- ~70 amendments with parsable filenames:
    {CONTRACT_ID}_{YYYY-MM-DD}_{COUNTERPARTY}_{DOCTYPE}.pdf
- ~500 contract document chunks with realistic clause language covering:
    CURTAILMENT, DELIVERY_FAILURE, RA_REMEDY, METERING, EANEP, DEGRADATION, PRICING
- Metering configs with deliberate mismatches (paid by SCE, ISO meter present)

Outputs parquet files to ./data/synthetic/  (relative to repo root).
"""

from __future__ import annotations

import json
import os
import random
import uuid
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

np.random.seed(7)
random.seed(7)

OUT_DIR = Path(__file__).resolve().parent.parent / "data" / "synthetic"
OUT_DIR.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------------
# Reference lists
# ---------------------------------------------------------------------------
COUNTERPARTIES = [
    ("CP-001", "Mojave Solar Ventures LLC",         "DEVELOPER", "CA"),
    ("CP-002", "Tehachapi Wind Holdings",            "IPP",       "CA"),
    ("CP-003", "Crimson BESS Operating",             "DEVELOPER", "CA"),
    ("CP-004", "Kingbird Solar Partners",            "DEVELOPER", "CA"),
    ("CP-005", "Coyote Creek Energy",                "IPP",       "CA"),
    ("CP-006", "Daggett Battery Storage",            "DEVELOPER", "CA"),
    ("CP-007", "Antelope Valley Renewables",        "DEVELOPER", "CA"),
    ("CP-008", "Westlands Solar Farms",              "DEVELOPER", "CA"),
    ("CP-009", "Pacific Energy Trading",             "TRADER",    "CA"),
    ("CP-010", "Calpine Mojave Generation",          "IPP",       "CA"),
    ("CP-011", "Sun Streams BESS",                   "DEVELOPER", "AZ"),
    ("CP-012", "Riverside Public Utilities",         "UTILITY",   "CA"),
    ("CP-013", "EDF Renewables Desert",              "DEVELOPER", "CA"),
    ("CP-014", "NextEra California Wind",            "IPP",       "CA"),
    ("CP-015", "Clearway Mojave Solar",              "DEVELOPER", "CA"),
]

RESOURCE_TYPES = ["SOLAR", "WIND", "BATTERY", "HYBRID_SOLAR_BESS", "GAS"]
CONTRACT_TYPES = ["PPA", "RA", "TOLLING", "HYBRID"]
CURTAILMENT_TYPES = ["ECONOMIC", "RELIABILITY", "UNLIMITED_OPERATIONAL", "NONE"]
DELIVERY_POINTS = [
    "Vincent 500kV", "Antelope 230kV", "Kramer 230kV",
    "Lugo 500kV", "Devers 500kV", "Mira Loma 500kV",
]

DOC_TYPES = {
    "AMENDMENT":   ["Amendment", "First Amendment", "Second Amendment",
                    "Third Amendment", "Amendment_No_4", "Fifth_Amendment"],
    "RESTATEMENT": ["Amended_and_Restated", "Restated"],
    "SIDE_LETTER": ["Side_Letter", "Side_Agreement"],
    "NOTICE":      ["Notice_of_Curtailment", "Capacity_Notice"],
}

CHANGE_CATEGORY_POOL = [
    "CAPACITY", "CURTAILMENT", "PRICING", "TERM_EXTENSION",
    "DELIVERY_POINT", "METERING", "RA_RIGHTS", "EANEP_REVISION",
]


# ---------------------------------------------------------------------------
# 1.  COUNTERPARTY
# ---------------------------------------------------------------------------
counterparty_df = pd.DataFrame(
    COUNTERPARTIES,
    columns=["COUNTERPARTY_ID", "COUNTERPARTY_NAME", "COUNTERPARTY_TYPE", "HQ_STATE"],
)


# ---------------------------------------------------------------------------
# 2.  CONTRACT
# ---------------------------------------------------------------------------
contracts: list[dict] = []
N_CONTRACTS = 25

for i in range(1, N_CONTRACTS + 1):
    cp = COUNTERPARTIES[(i - 1) % len(COUNTERPARTIES)]
    resource = random.choice(RESOURCE_TYPES)
    contract_type = random.choice(CONTRACT_TYPES)
    capacity = round(random.choice([5, 8, 10, 15, 25, 50, 80, 100, 150, 200, 250]) +
                     random.uniform(-1, 3), 2)
    exec_dt = date(2018, 1, 1) + timedelta(days=random.randint(0, 365 * 6))
    term_start = exec_dt + timedelta(days=random.randint(180, 540))
    term_years = random.choice([10, 15, 20, 25])
    term_end = date(term_start.year + term_years, term_start.month, term_start.day)

    curtailment_flag = random.random() < 0.7
    curtailment_type = (
        random.choice(["ECONOMIC", "RELIABILITY", "UNLIMITED_OPERATIONAL"])
        if curtailment_flag else "NONE"
    )

    payment_meter = random.choices(["SCE", "ISO", "THIRD_PARTY"], weights=[0.5, 0.4, 0.1])[0]
    iso_meter_flag = random.random() < 0.65  # most have ISO meters

    contracts.append({
        "CONTRACT_ID": f"CTR-{i:03d}",
        "CONTRACT_NAME": f"{cp[1].split()[0]} {resource.title()} {contract_type}",
        "COUNTERPARTY_ID": cp[0],
        "CONTRACT_TYPE": contract_type,
        "RESOURCE_TYPE": resource,
        "CAPACITY_MW": capacity,
        "EXECUTION_DATE": exec_dt,
        "TERM_START_DATE": term_start,
        "TERM_END_DATE": term_end,
        "STATUS": random.choices(
            ["ACTIVE", "EXPIRED", "TERMINATED", "PROPOSED"],
            weights=[0.75, 0.1, 0.05, 0.1],
        )[0],
        "CURTAILMENT_FLAG": curtailment_flag,
        "CURTAILMENT_TYPE": curtailment_type,
        "CURTAILMENT_CAP_HRS": (
            random.choice([200, 350, 500, 750, 1000]) if curtailment_flag else None
        ),
        "PAYMENT_METER": payment_meter,
        "ISO_METER_FLAG": iso_meter_flag,
        "EANEP_FACTOR": round(random.uniform(0.18, 0.34), 4)
                        if resource in ("SOLAR", "WIND", "HYBRID_SOLAR_BESS") else None,
        "DEGRADATION_FACTOR": round(random.uniform(0.003, 0.010), 5)
                              if resource in ("SOLAR", "HYBRID_SOLAR_BESS") else None,
        "DELIVERY_POINT": random.choice(DELIVERY_POINTS),
        "POI_SUBSTATION": random.choice(DELIVERY_POINTS).split()[0],
        "BASE_PRICE_USD_MWH": round(random.uniform(28, 95), 2),
    })

contract_df = pd.DataFrame(contracts)


# ---------------------------------------------------------------------------
# 3.  AMENDMENT (parsable filenames)
# ---------------------------------------------------------------------------
amendments: list[dict] = []
amendment_seq = 1

for c in contracts:
    n_amendments = np.random.choice([0, 1, 2, 3, 4, 5], p=[0.15, 0.25, 0.25, 0.2, 0.10, 0.05])
    base_dt = c["EXECUTION_DATE"]
    for k in range(1, n_amendments + 1):
        exec_dt = base_dt + timedelta(days=180 * k + random.randint(0, 120))
        if exec_dt > date(2025, 12, 1):
            exec_dt = date(2025, 12, 1) - timedelta(days=random.randint(0, 90))

        doc_type = random.choices(
            list(DOC_TYPES.keys()),
            weights=[0.7, 0.15, 0.10, 0.05],
        )[0]
        doc_label = random.choice(DOC_TYPES[doc_type])

        cp_name_clean = (
            c["CONTRACT_NAME"].split()[0]
            .replace(" ", "_")
            .replace("/", "_")
        )
        # Filename pattern per requirements:
        # {CONTRACT_ID}_{YYYY-MM-DD}_{COUNTERPARTY}_{FREE_TEXT_INC_DOCTYPE}.pdf
        file_name = (
            f"{c['CONTRACT_ID']}_{exec_dt.isoformat()}_"
            f"{cp_name_clean}_{doc_label}.pdf"
        )

        change_cats = random.sample(
            CHANGE_CATEGORY_POOL, k=random.randint(1, 3)
        )

        # Realistic summary
        templates = [
            "Amends Section 3.2 to revise the curtailment cap from {old} to {new} hours per contract year.",
            "Increases nameplate capacity by {mw} MW and adjusts the EANEP from {old}% to {new}%.",
            "Extends the contract term by {yrs} years and revises the price escalator clause.",
            "Adds an alternate delivery point at {pt} and clarifies metering responsibilities.",
            "Updates remedy provisions for failure to deliver Resource Adequacy capacity.",
            "Modifies the degradation factor schedule and revises annual production guarantees.",
        ]
        summary = random.choice(templates).format(
            old=random.randint(200, 800),
            new=random.randint(300, 1200),
            mw=random.randint(2, 25),
            yrs=random.choice([3, 5, 7, 10]),
            pt=random.choice(DELIVERY_POINTS),
        )

        amendments.append({
            "AMENDMENT_ID": f"AMD-{amendment_seq:04d}",
            "CONTRACT_ID": c["CONTRACT_ID"],
            "AMENDMENT_NUMBER": k,
            "EXECUTION_DATE": exec_dt,
            "COUNTERPARTY_NAME": c["CONTRACT_NAME"].split()[0],
            "DOC_TYPE": doc_type,
            "FILE_NAME": file_name,
            "STAGE_PATH": f"@SCE_EPM_DB.RAW.PDF_STAGE/{file_name}",
            "PAGE_COUNT": random.randint(4, 28),
            "SUMMARY": summary,
            "CHANGE_CATEGORIES": json.dumps(change_cats),
        })
        amendment_seq += 1

amendment_df = pd.DataFrame(amendments)


# ---------------------------------------------------------------------------
# 4.  METERING_CONFIG
# ---------------------------------------------------------------------------
metering_rows = []
for c in contracts:
    iso_flag = c["ISO_METER_FLAG"]
    pay_meter = c["PAYMENT_METER"]
    mismatch = (pay_meter == "SCE") and iso_flag        # Q6 target
    metering_rows.append({
        "CONTRACT_ID": c["CONTRACT_ID"],
        "PAYMENT_METER": pay_meter,
        "SETTLEMENT_METER_ID": f"SET-{random.randint(10000, 99999)}",
        "ISO_METER_FLAG": iso_flag,
        "ISO_METER_ID": f"CAISO-{random.randint(10000, 99999)}" if iso_flag else None,
        "SCE_METER_ID": f"SCE-{random.randint(10000, 99999)}",
        "METERING_NOTES": (
            "Settlement performed against SCE revenue meter. "
            "Separate CAISO telemetry meter installed at POI."
            if mismatch else
            "Standard settlement configuration."
        ),
        "MISMATCH_FLAG": mismatch,
    })

metering_df = pd.DataFrame(metering_rows)


# ---------------------------------------------------------------------------
# 5.  CONTRACT_DOCUMENT_CHUNK   (the heart of Q2 / Q3 / Q5 / Q6 RAG)
# ---------------------------------------------------------------------------
CLAUSE_TEMPLATES: dict[str, list[str]] = {
    "CURTAILMENT": [
        "Buyer may curtail Seller's deliveries in whole or in part for economic reasons up to {cap} hours per Contract Year. Curtailment shall be communicated by Buyer with no less than {hr} hours prior notice via the CAISO scheduling interface.",
        "Reliability curtailment events directed by the CAISO shall not count against the annual curtailment cap and Seller shall not be entitled to any additional compensation for such events.",
        "In the event of unlimited operational curtailment, Seller waives any claim for lost revenue arising from Buyer-directed curtailment, except for events caused by Buyer's gross negligence.",
    ],
    "DELIVERY_FAILURE": [
        "If Seller fails to deliver at least {pct}% of the Expected Annual Net Energy Production for any Contract Year, Seller shall pay Buyer liquidated damages equal to the positive difference between the Replacement Price and the Contract Price multiplied by the deficiency in MWh.",
        "Seller's failure to achieve the guaranteed capacity for two consecutive months shall be a Product Deficiency event entitling Buyer to terminate the affected portion of the Contract Quantity.",
        "Seller's repeated under-delivery shall trigger a cure period of 90 days, after which Buyer may exercise its product deficiency remedies including suspension of capacity payments.",
    ],
    "RA_REMEDY": [
        "If Seller fails to deliver Resource Adequacy Capacity in any Showing Month, Buyer's sole remedy shall be liquidated damages calculated at $3.79/kW-month plus any CAISO penalties assessed against Buyer.",
        "Seller shall use commercially reasonable efforts to procure Replacement RA Capacity at Seller's cost. Failure to deliver Replacement RA shall be deemed a material breach.",
        "RA Capacity not delivered shall result in a deduction from the next Capacity Payment equal to 1.5x the deficient MW multiplied by the prevailing CPUC RA price benchmark.",
    ],
    "METERING": [
        "Settlement shall be performed against the SCE Revenue Meter installed at the Point of Interconnection. The CAISO meter, while installed for telemetry, shall not be used for settlement purposes.",
        "Both Parties acknowledge that a separate CAISO meter has been installed for telemetry. Payments under this Agreement shall be calculated solely from the SCE meter readings unless otherwise agreed in writing.",
        "In the event of a discrepancy greater than 0.5% between the SCE Meter and the CAISO Meter, the Parties shall reconcile readings within 30 days using meter testing per ANSI C12 standards.",
    ],
    "EANEP": [
        "The Expected Annual Net Energy Production (EANEP) for the Facility is {gwh} GWh in Contract Year 1, decreasing by the Degradation Factor each subsequent year.",
        "EANEP shall be re-baselined every five years based on a P50 production estimate prepared by an Independent Engineer mutually approved by the Parties.",
        "Failure to deliver at least 85% of EANEP averaged over any rolling 24-month period shall constitute a Performance Default.",
    ],
    "DEGRADATION": [
        "The Degradation Factor applicable to the Facility shall be {df}% per Contract Year, applied cumulatively to the EANEP.",
        "Module degradation in excess of {df}% per annum shall be deemed an Equipment Defect and Seller shall be obligated to remediate within 180 days.",
        "The Parties may, by mutual agreement, retain an Independent Engineer to validate observed degradation against the contractual Degradation Factor.",
    ],
    "PRICING": [
        "The Contract Price shall be ${price}/MWh, escalated annually by the lesser of (i) the GDP-IPD or (ii) 2.5%.",
        "Capacity Payments shall be made monthly at $/kW-month rate of ${cap}, prorated for partial months.",
    ],
    "TERMINATION": [
        "Either Party may terminate this Agreement upon 60 days' written notice if the other Party becomes insolvent or fails to cure a material breach within the cure period.",
    ],
    "TERM": [
        "The Initial Term shall commence on the Commercial Operation Date and continue for {yrs} years, unless terminated earlier in accordance with this Agreement.",
    ],
    "GENERAL": [
        "This Agreement shall be governed by the laws of the State of California, without regard to conflicts of law principles.",
        "Notices required under this Agreement shall be delivered to the addresses set forth in Exhibit B and shall be deemed effective upon receipt.",
    ],
}


def render_clause(clause_type: str, ctx: dict) -> str:
    template = random.choice(CLAUSE_TEMPLATES[clause_type])
    return template.format(
        cap=ctx.get("cap", random.choice([200, 350, 500, 750])),
        hr=random.choice([2, 4, 6, 12]),
        pct=random.choice([85, 90, 95]),
        gwh=round(ctx.get("gwh", 250) * random.uniform(0.6, 1.4), 1),
        df=round(ctx.get("df", 0.005) * 100, 3),
        price=round(ctx.get("price", 50), 2),
        yrs=random.choice([10, 15, 20, 25]),
    )


chunks: list[dict] = []
chunk_seq = 1

for c in contracts:
    capacity = c["CAPACITY_MW"]
    eanep_gwh = (c["EANEP_FACTOR"] or 0.25) * capacity * 8760 / 1000
    ctx = {
        "cap": c["CURTAILMENT_CAP_HRS"] or 500,
        "gwh": eanep_gwh,
        "df": c["DEGRADATION_FACTOR"] or 0.005,
        "price": c["BASE_PRICE_USD_MWH"],
    }

    # Base-contract chunks: cover all clause types once per contract
    base_clauses = ["CURTAILMENT", "DELIVERY_FAILURE", "RA_REMEDY",
                    "METERING", "EANEP", "DEGRADATION", "PRICING",
                    "TERM", "TERMINATION", "GENERAL"]
    if not c["CURTAILMENT_FLAG"]:
        base_clauses = [x for x in base_clauses if x != "CURTAILMENT"]
    if c["CONTRACT_TYPE"] != "RA":
        # Most non-RA still have RA-related riders; keep but lower frequency
        if random.random() < 0.5:
            base_clauses = [x for x in base_clauses if x != "RA_REMEDY"]
    if c["RESOURCE_TYPE"] not in ("SOLAR", "HYBRID_SOLAR_BESS"):
        base_clauses = [x for x in base_clauses if x != "DEGRADATION"]

    page = 1
    for clause in base_clauses:
        for _ in range(random.choice([1, 2])):
            chunks.append({
                "CHUNK_ID": f"CHK-{chunk_seq:05d}",
                "CONTRACT_ID": c["CONTRACT_ID"],
                "AMENDMENT_ID": None,
                "DOC_TYPE": "BASE_CONTRACT",
                "SECTION_TITLE": f"Section {random.randint(2, 18)}.{random.randint(1, 9)} {clause.title().replace('_',' ')}",
                "CLAUSE_TYPE": clause,
                "PAGE_NUMBER": page,
                "CONTENT": render_clause(clause, ctx),
                "SOURCE_FILE": f"{c['CONTRACT_ID']}_BASE_CONTRACT.pdf",
            })
            page += 1
            chunk_seq += 1

# Amendment chunks: one per amendment with relevant clause modifications
for a in amendments:
    cat_list = json.loads(a["CHANGE_CATEGORIES"])
    cat_to_clause = {
        "CAPACITY":        "EANEP",
        "CURTAILMENT":     "CURTAILMENT",
        "PRICING":         "PRICING",
        "TERM_EXTENSION":  "TERM",
        "DELIVERY_POINT":  "GENERAL",
        "METERING":        "METERING",
        "RA_RIGHTS":       "RA_REMEDY",
        "EANEP_REVISION":  "EANEP",
    }
    related_contract = next(c for c in contracts if c["CONTRACT_ID"] == a["CONTRACT_ID"])
    capacity = related_contract["CAPACITY_MW"]
    ctx = {
        "cap": related_contract["CURTAILMENT_CAP_HRS"] or 500,
        "gwh": (related_contract["EANEP_FACTOR"] or 0.25) * capacity * 8760 / 1000,
        "df": related_contract["DEGRADATION_FACTOR"] or 0.005,
        "price": related_contract["BASE_PRICE_USD_MWH"],
    }
    for cat in cat_list:
        clause = cat_to_clause.get(cat, "GENERAL")
        chunks.append({
            "CHUNK_ID": f"CHK-{chunk_seq:05d}",
            "CONTRACT_ID": a["CONTRACT_ID"],
            "AMENDMENT_ID": a["AMENDMENT_ID"],
            "DOC_TYPE": a["DOC_TYPE"],
            "SECTION_TITLE": f"Amendment {a['AMENDMENT_NUMBER']} — {cat.replace('_',' ').title()}",
            "CLAUSE_TYPE": clause,
            "PAGE_NUMBER": random.randint(1, max(2, a["PAGE_COUNT"])),
            "CONTENT": (
                f"Pursuant to {a['DOC_TYPE'].replace('_',' ').title()} #{a['AMENDMENT_NUMBER']} "
                f"executed {a['EXECUTION_DATE'].isoformat()}: "
                + render_clause(clause, ctx)
            ),
            "SOURCE_FILE": a["FILE_NAME"],
        })
        chunk_seq += 1

chunk_df = pd.DataFrame(chunks)


# ---------------------------------------------------------------------------
# 6.  Persist parquet
# ---------------------------------------------------------------------------
counterparty_df.to_parquet(OUT_DIR / "counterparty.parquet", index=False)
contract_df.to_parquet(OUT_DIR / "contract.parquet", index=False)
amendment_df.to_parquet(OUT_DIR / "amendment.parquet", index=False)
metering_df.to_parquet(OUT_DIR / "metering_config.parquet", index=False)
chunk_df.to_parquet(OUT_DIR / "contract_document_chunk.parquet", index=False)

print(f"Wrote synthetic data to {OUT_DIR}")
print(f"  counterparties:           {len(counterparty_df):>5}")
print(f"  contracts:                {len(contract_df):>5}")
print(f"  amendments:               {len(amendment_df):>5}")
print(f"  metering configs:         {len(metering_df):>5}")
print(f"  document chunks:          {len(chunk_df):>5}")
print(f"  Q6 metering mismatches:   {int(metering_df['MISMATCH_FLAG'].sum()):>5}")
print(f"  Q3 curtailment contracts: {int(contract_df['CURTAILMENT_FLAG'].sum()):>5}")
print(f"  Q4 contracts > 10 MW:     {int((contract_df['CAPACITY_MW'] > 10).sum()):>5}")
