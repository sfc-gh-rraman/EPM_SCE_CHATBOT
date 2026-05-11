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
            COUNT(*)                          AS contract_count,
            SUM(CASE WHEN STATUS='ACTIVE' THEN 1 ELSE 0 END) AS active_contracts,
            ROUND(SUM(CAPACITY_MW), 1)        AS total_capacity_mw,
            COUNT(DISTINCT SUPPLIER)          AS supplier_count
        FROM SCE_EPM_DB.CONTRACTS.CONTRACT_SUMMARY_V
    """
    rows = sf.execute_query(sql)
    return rows[0] if rows else {}
