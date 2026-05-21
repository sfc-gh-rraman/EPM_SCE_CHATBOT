"""
SCE EPM Contract Chatbot — FastAPI Main Application

Thin FastAPI service that streams responses from a Snowflake Cortex Agent
(SCE_EPM_CONTRACT_AGENT) over SSE, plus a few helper endpoints that surface
structured data directly from the SCE_EPM_DB.CONTRACTS analytics views.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sys

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Any, Dict, List, Optional

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# ---------------------------------------------------------------------------
# Lazy service initialisation
# ---------------------------------------------------------------------------
_snowflake_service = None
_cortex_agent_client = None


def get_sf():
    global _snowflake_service
    if _snowflake_service is None:
        from services.snowflake_service_spcs import get_snowflake_service
        _snowflake_service = get_snowflake_service()
    return _snowflake_service


def get_agent():
    global _cortex_agent_client
    if _cortex_agent_client is None:
        from services.cortex_agent_client import get_cortex_agent_client
        _cortex_agent_client = get_cortex_agent_client()
    return _cortex_agent_client


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------
app = FastAPI(
    title="SCE EPM Contract Chatbot API",
    description="Conversational interface over SCE PPA / RA / Tolling contracts and amendments.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------
class ChatMessage(BaseModel):
    message: str
    contract_id: Optional[str] = None
    history: Optional[List[Dict[str, Any]]] = None


class ChatResponse(BaseModel):
    response: str
    sources: List[str] = []
    context: Dict[str, Any] = {}


# ---------------------------------------------------------------------------
# Health / info
# ---------------------------------------------------------------------------
@app.get("/health")
async def health():
    return {"status": "healthy", "service": "sce-epm-contract-chatbot"}


@app.get("/api/info")
async def api_info():
    return {
        "name": "SCE EPM Contract Chatbot API",
        "version": "1.0.0",
        "description": "Cortex Agent over SCE EPM contract semantic model + clause search.",
        "sample_questions": [
            "How many amendments does CTR-001 have, and what does each one cover?",
            "What changed in the most recent amendment to CTR-005?",
            "Show me contracts with economic curtailment terms.",
            "Show me contracts with capacity > 10 MW.",
            "How do our contracts handle product deficiency or failure to deliver Resource Adequacy?",
            "Which contracts are paid by SCE meter but have a separate ISO meter?",
        ],
    }


# ---------------------------------------------------------------------------
# Chat — non-streaming (collects full response)
# ---------------------------------------------------------------------------
@app.post("/api/chat", response_model=ChatResponse)
async def chat(message: ChatMessage):
    try:
        agent = get_agent()
        full_text_parts: List[str] = []
        sources: List[str] = []
        async for event in agent.run_agent(message.message, conversation_history=message.history):
            etype = event.get("type")
            if etype == "text":
                full_text_parts.append(event.get("content", ""))
            elif etype == "tool_result":
                src = event.get("source")
                if src and src not in sources:
                    sources.append(src)
        return ChatResponse(
            response="".join(full_text_parts).strip(),
            sources=sources,
            context={},
        )
    except Exception as exc:
        logger.exception("chat error")
        raise HTTPException(status_code=500, detail=str(exc))


# ---------------------------------------------------------------------------
# Chat — SSE stream
# ---------------------------------------------------------------------------
@app.post("/api/chat/stream")
async def chat_stream(message: ChatMessage):
    async def event_generator():
        try:
            agent = get_agent()
            yield f"data: {json.dumps({'type': 'thinking', 'title': 'Planning', 'content': 'Analyzing your question...'})}\n\n"
            async for event in agent.run_agent(message.message, conversation_history=message.history):
                yield f"data: {json.dumps(event)}\n\n"
                await asyncio.sleep(0.01)
            yield "data: [DONE]\n\n"
        except Exception as exc:
            logger.exception("chat_stream error")
            yield f"data: {json.dumps({'type': 'error', 'content': str(exc)})}\n\n"
            yield "data: [DONE]\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


# ---------------------------------------------------------------------------
# Helper endpoints — structured data straight from CONTRACTS schema
# ---------------------------------------------------------------------------
@app.get("/api/contracts")
async def list_contracts(
    min_capacity_mw: Optional[float] = None,
    status: Optional[str] = None,
    contract_type: Optional[str] = None,
):
    sf = get_sf()
    where = ["1=1"]
    if min_capacity_mw is not None:
        where.append(f"CAPACITY_MW > {float(min_capacity_mw)}")
    if status:
        where.append(f"STATUS = '{status.upper()}'")
    if contract_type:
        where.append(f"CONTRACT_TYPE = '{contract_type.upper()}'")
    sql = f"""
        SELECT CONTRACT_ID, CONTRACT_NAME, SUPPLIER, CONTRACT_TYPE,
               RESOURCE_TYPE, CAPACITY_MW, EXECUTION_DATE, TERM_START_DATE,
               TERM_END_DATE, STATUS
        FROM SCE_EPM_DB.CONTRACTS.CONTRACT_SUMMARY_V
        WHERE {' AND '.join(where)}
        ORDER BY CAPACITY_MW DESC
        LIMIT 200
    """
    return {"rows": sf.execute_query(sql)}


@app.get("/api/contracts/{contract_id}/amendments")
async def amendments_for_contract(contract_id: str):
    sf = get_sf()
    sql = f"""
        SELECT AMENDMENT_NUMBER, EXECUTION_DATE, DOC_TYPE, FILE_NAME,
               PAGE_COUNT, SUMMARY
        FROM SCE_EPM_DB.CONTRACTS.AMENDMENT_DETAIL_V
        WHERE CONTRACT_ID = '{contract_id}'
        ORDER BY AMENDMENT_NUMBER
    """
    return {"contract_id": contract_id, "amendments": sf.execute_query(sql)}


@app.get("/api/contracts/curtailment")
async def curtailment_contracts(curtailment_type: Optional[str] = None):
    sf = get_sf()
    where = "CURTAILMENT_FLAG = TRUE"
    if curtailment_type:
        where += f" AND CURTAILMENT_TYPE = '{curtailment_type.upper()}'"
    sql = f"""
        SELECT CONTRACT_ID, CONTRACT_NAME, SUPPLIER, RESOURCE_TYPE,
               CAPACITY_MW, CURTAILMENT_TYPE, CURTAILMENT_CAP_HRS, STATUS
        FROM SCE_EPM_DB.CONTRACTS.CONTRACT_CURTAILMENT_V
        WHERE {where}
        ORDER BY CAPACITY_MW DESC
    """
    return {"rows": sf.execute_query(sql)}


@app.get("/api/contracts/metering-mismatch")
async def metering_mismatch():
    sf = get_sf()
    sql = """
        SELECT CONTRACT_ID, CONTRACT_NAME, SUPPLIER, CAPACITY_MW,
               PAYMENT_METER, SCE_METER_ID, ISO_METER_ID, METERING_NOTES
        FROM SCE_EPM_DB.CONTRACTS.METERING_MISMATCH_V
        ORDER BY CAPACITY_MW DESC
    """
    return {"rows": sf.execute_query(sql)}


@app.get("/api/portfolio/summary")
async def portfolio_summary():
    sf = get_sf()
    sql = """
        SELECT
            COUNT(*)                                              AS contract_count,
            COUNT(DISTINCT COUNTERPARTY_ID)                       AS counterparty_count,
            COUNT(DISTINCT CASE WHEN a.AMENDMENT_ID IS NOT NULL THEN a.CONTRACT_ID END) AS contracts_with_amendments,
            (SELECT COUNT(*) FROM SCE_EPM_DB.ATOMIC.AMENDMENT)   AS total_amendments,
            (SELECT COUNT(*) FROM SCE_EPM_DB.ATOMIC.CONTRACT_DOCUMENT_CHUNK) AS total_chunks
        FROM SCE_EPM_DB.ATOMIC.CONTRACT c
        LEFT JOIN SCE_EPM_DB.ATOMIC.AMENDMENT a ON a.CONTRACT_ID = c.CONTRACT_ID
    """
    rows = sf.execute_query(sql)
    base = rows[0] if rows else {}

    clause_sql = """
        SELECT CLAUSE_TYPE, COUNT(*) AS cnt
        FROM SCE_EPM_DB.ATOMIC.CONTRACT_DOCUMENT_CHUNK
        GROUP BY CLAUSE_TYPE ORDER BY cnt DESC
    """
    base["clause_distribution"] = sf.execute_query(clause_sql)

    top_counterparties_sql = """
        SELECT cp.COUNTERPARTY_NAME, COUNT(c.CONTRACT_ID) AS contracts
        FROM SCE_EPM_DB.ATOMIC.CONTRACT c
        JOIN SCE_EPM_DB.ATOMIC.COUNTERPARTY cp USING (COUNTERPARTY_ID)
        GROUP BY cp.COUNTERPARTY_NAME ORDER BY contracts DESC LIMIT 10
    """
    base["top_counterparties"] = sf.execute_query(top_counterparties_sql)

    amendment_velocity_sql = """
        SELECT DATE_TRUNC('month', EXECUTION_DATE) AS month, COUNT(*) AS cnt
        FROM SCE_EPM_DB.ATOMIC.AMENDMENT
        WHERE EXECUTION_DATE IS NOT NULL
        GROUP BY month ORDER BY month
    """
    base["amendment_velocity"] = sf.execute_query(amendment_velocity_sql)

    return base


@app.get("/api/contracts/all")
async def all_contracts():
    sf = get_sf()
    sql = """
        SELECT c.CONTRACT_ID, c.CONTRACT_NAME, cp.COUNTERPARTY_NAME AS SUPPLIER,
               c.CONTRACT_TYPE, c.RESOURCE_TYPE, c.CAPACITY_MW,
               c.EXECUTION_DATE, c.TERM_START_DATE, c.TERM_END_DATE, c.STATUS,
               (SELECT COUNT(*) FROM SCE_EPM_DB.ATOMIC.AMENDMENT a WHERE a.CONTRACT_ID = c.CONTRACT_ID) AS amendment_count,
               (SELECT COUNT(*) FROM SCE_EPM_DB.ATOMIC.CONTRACT_DOCUMENT_CHUNK ck WHERE ck.CONTRACT_ID = c.CONTRACT_ID) AS chunk_count
        FROM SCE_EPM_DB.ATOMIC.CONTRACT c
        LEFT JOIN SCE_EPM_DB.ATOMIC.COUNTERPARTY cp USING (COUNTERPARTY_ID)
        ORDER BY c.CONTRACT_NAME
    """
    return {"rows": sf.execute_query(sql)}


@app.get("/api/contracts/{contract_id}/deep-dive")
async def contract_deep_dive(contract_id: str):
    sf = get_sf()
    contract_sql = f"""
        SELECT c.*, cp.COUNTERPARTY_NAME AS SUPPLIER
        FROM SCE_EPM_DB.ATOMIC.CONTRACT c
        LEFT JOIN SCE_EPM_DB.ATOMIC.COUNTERPARTY cp USING (COUNTERPARTY_ID)
        WHERE c.CONTRACT_ID = '{contract_id}'
    """
    contract_rows = sf.execute_query(contract_sql)
    contract = contract_rows[0] if contract_rows else {}

    amendments_sql = f"""
        SELECT AMENDMENT_ID, AMENDMENT_NUMBER, EXECUTION_DATE, DOC_TYPE, FILE_NAME
        FROM SCE_EPM_DB.ATOMIC.AMENDMENT
        WHERE CONTRACT_ID = '{contract_id}'
        ORDER BY AMENDMENT_NUMBER
    """
    amendments = sf.execute_query(amendments_sql)

    clause_dist_sql = f"""
        SELECT CLAUSE_TYPE, COUNT(*) AS cnt
        FROM SCE_EPM_DB.ATOMIC.CONTRACT_DOCUMENT_CHUNK
        WHERE CONTRACT_ID = '{contract_id}'
        GROUP BY CLAUSE_TYPE ORDER BY cnt DESC
    """
    clause_dist = sf.execute_query(clause_dist_sql)

    return {"contract": contract, "amendments": amendments, "clause_distribution": clause_dist}


@app.get("/api/clauses/analytics")
async def clause_analytics():
    sf = get_sf()
    distribution_sql = """
        SELECT CLAUSE_TYPE, COUNT(*) AS chunk_count,
               COUNT(DISTINCT CONTRACT_ID) AS contract_count
        FROM SCE_EPM_DB.ATOMIC.CONTRACT_DOCUMENT_CHUNK
        GROUP BY CLAUSE_TYPE ORDER BY chunk_count DESC
    """
    distribution = sf.execute_query(distribution_sql)

    top_curtailment_sql = """
        SELECT ck.CONTRACT_ID, c.CONTRACT_NAME, cp.COUNTERPARTY_NAME, COUNT(*) AS curtailment_chunks
        FROM SCE_EPM_DB.ATOMIC.CONTRACT_DOCUMENT_CHUNK ck
        JOIN SCE_EPM_DB.ATOMIC.CONTRACT c ON c.CONTRACT_ID = ck.CONTRACT_ID
        LEFT JOIN SCE_EPM_DB.ATOMIC.COUNTERPARTY cp ON cp.COUNTERPARTY_ID = c.COUNTERPARTY_ID
        WHERE ck.CLAUSE_TYPE = 'CURTAILMENT'
        GROUP BY ck.CONTRACT_ID, c.CONTRACT_NAME, cp.COUNTERPARTY_NAME
        ORDER BY curtailment_chunks DESC LIMIT 15
    """
    top_curtailment = sf.execute_query(top_curtailment_sql)

    doc_type_sql = """
        SELECT DOC_TYPE, COUNT(*) AS chunks, COUNT(DISTINCT CONTRACT_ID) AS contracts
        FROM SCE_EPM_DB.ATOMIC.CONTRACT_DOCUMENT_CHUNK
        GROUP BY DOC_TYPE ORDER BY chunks DESC
    """
    by_doc_type = sf.execute_query(doc_type_sql)

    return {"distribution": distribution, "top_curtailment": top_curtailment, "by_doc_type": by_doc_type}


@app.post("/api/contracts/search")
async def search_contracts(body: Dict[str, Any]):
    sf = get_sf()
    query = body.get("query", "")
    limit = body.get("limit", 20)
    clause_type = body.get("clause_type")

    keywords = [w.strip().lower() for w in query.split() if len(w.strip()) > 2]
    if not keywords:
        return {"results": []}

    like_conds = " OR ".join([f"LOWER(ck.CONTENT) LIKE '%{kw}%'" for kw in keywords[:5]])
    clause_filter = f"AND ck.CLAUSE_TYPE = '{clause_type}'" if clause_type else ""

    sql = f"""
        SELECT ck.CHUNK_ID, ck.CONTRACT_ID, c.CONTRACT_NAME, cp.COUNTERPARTY_NAME,
               ck.CLAUSE_TYPE, ck.DOC_TYPE, SUBSTR(ck.CONTENT, 1, 400) AS snippet
        FROM SCE_EPM_DB.ATOMIC.CONTRACT_DOCUMENT_CHUNK ck
        JOIN SCE_EPM_DB.ATOMIC.CONTRACT c ON c.CONTRACT_ID = ck.CONTRACT_ID
        LEFT JOIN SCE_EPM_DB.ATOMIC.COUNTERPARTY cp ON cp.COUNTERPARTY_ID = c.COUNTERPARTY_ID
        WHERE ({like_conds}) {clause_filter}
        LIMIT {int(limit)}
    """
    return {"results": sf.execute_query(sql)}


@app.get("/api/daily-brief")
async def daily_brief():
    sf = get_sf()
    stats_sql = """
        SELECT
            (SELECT COUNT(*) FROM SCE_EPM_DB.ATOMIC.CONTRACT) AS total_contracts,
            (SELECT COUNT(*) FROM SCE_EPM_DB.ATOMIC.AMENDMENT) AS total_amendments,
            (SELECT COUNT(DISTINCT COUNTERPARTY_ID) FROM SCE_EPM_DB.ATOMIC.CONTRACT) AS counterparties,
            (SELECT COUNT(*) FROM SCE_EPM_DB.ATOMIC.CONTRACT_DOCUMENT_CHUNK WHERE CLAUSE_TYPE='CURTAILMENT') AS curtailment_clauses,
            (SELECT COUNT(*) FROM SCE_EPM_DB.ATOMIC.CONTRACT_DOCUMENT_CHUNK WHERE CLAUSE_TYPE='DELIVERY_FAILURE') AS delivery_failure_clauses
    """
    stats = sf.execute_query(stats_sql)

    recent_amendments_sql = """
        SELECT a.AMENDMENT_ID, a.CONTRACT_ID, c.CONTRACT_NAME, cp.COUNTERPARTY_NAME,
               a.DOC_TYPE, a.EXECUTION_DATE, a.FILE_NAME
        FROM SCE_EPM_DB.ATOMIC.AMENDMENT a
        JOIN SCE_EPM_DB.ATOMIC.CONTRACT c ON c.CONTRACT_ID = a.CONTRACT_ID
        LEFT JOIN SCE_EPM_DB.ATOMIC.COUNTERPARTY cp ON cp.COUNTERPARTY_ID = c.COUNTERPARTY_ID
        WHERE a.EXECUTION_DATE IS NOT NULL
        ORDER BY a.EXECUTION_DATE DESC
        LIMIT 10
    """
    recent = sf.execute_query(recent_amendments_sql)

    high_amendment_sql = """
        SELECT c.CONTRACT_ID, c.CONTRACT_NAME, cp.COUNTERPARTY_NAME, COUNT(a.AMENDMENT_ID) AS amd_count
        FROM SCE_EPM_DB.ATOMIC.CONTRACT c
        JOIN SCE_EPM_DB.ATOMIC.AMENDMENT a ON a.CONTRACT_ID = c.CONTRACT_ID
        LEFT JOIN SCE_EPM_DB.ATOMIC.COUNTERPARTY cp ON cp.COUNTERPARTY_ID = c.COUNTERPARTY_ID
        GROUP BY c.CONTRACT_ID, c.CONTRACT_NAME, cp.COUNTERPARTY_NAME
        HAVING COUNT(a.AMENDMENT_ID) >= 5
        ORDER BY amd_count DESC LIMIT 10
    """
    high_amendment = sf.execute_query(high_amendment_sql)

    return {"stats": stats[0] if stats else {}, "recent_amendments": recent, "high_amendment_contracts": high_amendment}


@app.get("/api/resource-map")
async def resource_map():
    sf = get_sf()
    sql = """
        SELECT cp.COUNTERPARTY_NAME, c.CONTRACT_TYPE, c.RESOURCE_TYPE,
               COUNT(*) AS contract_count
        FROM SCE_EPM_DB.ATOMIC.CONTRACT c
        LEFT JOIN SCE_EPM_DB.ATOMIC.COUNTERPARTY cp USING (COUNTERPARTY_ID)
        GROUP BY cp.COUNTERPARTY_NAME, c.CONTRACT_TYPE, c.RESOURCE_TYPE
        ORDER BY contract_count DESC
    """
    by_counterparty = sf.execute_query(sql)

    doc_type_sql = """
        SELECT DOC_TYPE, COUNT(*) AS doc_count
        FROM SCE_EPM_DB.ATOMIC.AMENDMENT
        GROUP BY DOC_TYPE ORDER BY doc_count DESC
    """
    by_doc_type = sf.execute_query(doc_type_sql)

    return {"by_counterparty": by_counterparty, "by_doc_type": by_doc_type}
