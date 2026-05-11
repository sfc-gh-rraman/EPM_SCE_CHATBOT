"""
Cortex Agent REST API Client

Calls the Snowflake Cortex Agents REST API and streams responses
including "thinking steps" back to the frontend via SSE.
"""

import os
import json
import logging
import ssl
import httpx
from typing import AsyncGenerator, Optional, Dict, Any, List

logger = logging.getLogger(__name__)


class CortexAgentClient:
    """
    Client for calling Snowflake Cortex Agents REST API.

    Endpoint: POST /api/v2/databases/{db}/schemas/{schema}/agents/{name}:run

    Authentication:
      * SPCS deployment: OAuth token from /snowflake/session/token
      * Local dev:       session token via snowflake-connector-python
                         using connection_name from SNOWFLAKE_CONNECTION_NAME
    """

    def __init__(self):
        self.database   = os.environ.get("SNOWFLAKE_DATABASE",      "SCE_EPM_DB")
        self.schema     = os.environ.get("SNOWFLAKE_AGENT_SCHEMA",  "CORTEX")
        self.agent_name = os.environ.get("SNOWFLAKE_AGENT_NAME",    "SCE_EPM_CONTRACT_AGENT")
        self.host       = os.environ.get("SNOWFLAKE_HOST", "")
        self.connection_name = os.environ.get("SNOWFLAKE_CONNECTION_NAME", "my_snowflake")
        self._sf_conn   = None
        self._token     = None
        self._is_spcs   = os.path.exists("/snowflake/session/token")

        logger.info(
            f"CortexAgentClient initialized: db={self.database}, schema={self.schema}, "
            f"agent={self.agent_name}, mode={'SPCS' if self._is_spcs else 'LOCAL'}"
        )
    
    def _get_token(self) -> str:
        """Get OAuth/session token (cached)."""
        # SPCS: read mounted token file every call (auto-refreshes on expiry)
        if self._is_spcs:
            with open("/snowflake/session/token", "r") as f:
                return f.read().strip()

        # Local dev: use snowflake-connector-python session token
        if self._sf_conn is None:
            import snowflake.connector
            self._sf_conn = snowflake.connector.connect(connection_name=self.connection_name)
            logger.info(f"Opened Snowflake connection '{self.connection_name}'")
        return self._sf_conn.rest.token

    def _get_host(self) -> str:
        if self.host:
            return self.host
        if self._sf_conn is not None:
            return self._sf_conn.host
        # Open the connection just to discover host
        import snowflake.connector
        self._sf_conn = snowflake.connector.connect(connection_name=self.connection_name)
        return self._sf_conn.host
    
    def _get_base_url(self) -> str:
        host = self._get_host()
        if not host:
            raise RuntimeError("Snowflake host could not be resolved")
        return f"https://{host}"
    
    def _get_agent_url(self) -> str:
        """Get the agent run endpoint URL - named agent format."""
        base = self._get_base_url()
        # Named agent endpoint: /api/v2/databases/{db}/schemas/{schema}/agents/{name}:run
        return f"{base}/api/v2/databases/{self.database}/schemas/{self.schema}/agents/{self.agent_name}:run"
    
    def _format_messages_for_api(self, messages: List[Dict[str, str]]) -> List[Dict[str, Any]]:
        """
        Format messages for Cortex Agent API.
        
        The API expects content to be an array of content objects:
        {"role": "user", "content": [{"type": "text", "text": "..."}]}
        
        NOT a bare string:
        {"role": "user", "content": "..."} <-- WRONG
        """
        formatted = []
        for msg in messages:
            formatted.append({
                "role": msg["role"],
                "content": [
                    {
                        "type": "text",
                        "text": msg["content"]
                    }
                ]
            })
        return formatted
    
    async def run_agent_stream(
        self,
        messages: List[Dict[str, str]],
        conversation_id: Optional[str] = None
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Call the Cortex Agent REST API with streaming enabled.
        
        Yields events including:
        - type: "thinking" - Planning/reasoning steps
        - type: "text" - Response text chunks
        - type: "tool_use" - SQL execution info
        - type: "done" - Stream complete
        - type: "error" - Error occurred
        
        Args:
            messages: List of message dicts with 'role' and 'content'
            conversation_id: Optional conversation ID for context
            
        Yields:
            Event dicts with type and data
        """
        try:
            token = self._get_token()
            url = self._get_agent_url()

            # SPCS uses Bearer + OAUTH; local dev with session token uses
            # `Snowflake Token="..."` auth header.
            if self._is_spcs:
                headers = {
                    "Authorization":                       f"Bearer {token}",
                    "X-Snowflake-Authorization-Token-Type": "OAUTH",
                    "Content-Type":  "application/json",
                    "Accept":        "text/event-stream",
                }
            else:
                headers = {
                    "Authorization": f'Snowflake Token="{token}"',
                    "Content-Type":  "application/json",
                    "Accept":        "text/event-stream",
                }
            
            # Format messages for Cortex Agent API - content must be array of objects!
            formatted_messages = self._format_messages_for_api(messages)
            
            body = {
                "messages": formatted_messages,
                "stream": True,
            }
            
            if conversation_id:
                body["thread_id"] = conversation_id
            
            logger.info(f"Request body: {json.dumps(body)[:500]}")
            
            logger.info(f"Calling Cortex Agent: {url}")
            logger.debug(f"Request body: {json.dumps(body)[:200]}")
            
            # Local hosts may have underscores that fail strict SSL hostname check;
            # use a permissive verify=False for local dev only (SPCS uses internal cert).
            verify_ssl = self._is_spcs

            async with httpx.AsyncClient(timeout=120.0, verify=verify_ssl) as client:
                async with client.stream(
                    "POST",
                    url,
                    headers=headers,
                    json=body,
                ) as response:
                    if response.status_code != 200:
                        error_text = await response.aread()
                        logger.error(f"Agent API error: {response.status_code} - {error_text}")
                        yield {
                            "type": "error",
                            "content": f"Agent API error: {response.status_code}",
                            "details": error_text.decode() if error_text else ""
                        }
                        return
                    
                    # Process SSE stream
                    buffer = ""
                    async for chunk in response.aiter_text():
                        buffer += chunk
                        
                        # Process complete events (separated by double newlines)
                        while "\n\n" in buffer:
                            event_str, buffer = buffer.split("\n\n", 1)
                            
                            # Parse SSE event
                            event = self._parse_sse_event(event_str)
                            if event:
                                yield event
                    
                    # Process any remaining buffer
                    if buffer.strip():
                        event = self._parse_sse_event(buffer)
                        if event:
                            yield event
            
            yield {"type": "done"}
            
        except Exception as e:
            logger.error(f"Cortex Agent stream error: {e}")
            yield {
                "type": "error",
                "content": str(e)
            }
    
    def _parse_sse_event(self, event_str: str) -> Optional[Dict[str, Any]]:
        """
        Parse an SSE event string from Cortex Agent API.
        
        Event types from Cortex Agent:
        - response.output_text.delta - ACTUAL OUTPUT TEXT (display to user)
        - response.thinking.delta - Agent's internal reasoning (show in thinking panel)
        - response.status - Status updates (planning, reasoning, etc.)
        - response.tool_result - Tool execution results (SQL, search)
        - response.tool_result.status - Tool execution status
        """
        try:
            lines = event_str.strip().split("\n")
            event_type = None
            data = None
            
            for line in lines:
                if line.startswith("event:"):
                    event_type = line[6:].strip()
                elif line.startswith("data:"):
                    data_str = line[5:].strip()
                    if data_str == "[DONE]":
                        return {"type": "done"}
                    try:
                        data = json.loads(data_str)
                    except json.JSONDecodeError:
                        data = {"raw": data_str}
            
            if data is None:
                return None
            
            # Log raw event for debugging - INFO level to capture all events
            logger.info(f"SSE: type={event_type}")
            
            if not isinstance(data, dict):
                return {"type": "text", "content": str(data)}
            
            # ============================================================
            # CRITICAL: Only response.output_text.delta is user-visible text
            # ============================================================
            
            if event_type == "response.output_text.delta" or event_type == "response.text.delta":
                # This is the ACTUAL response text to show the user
                text = data.get("text", "")
                if text:
                    return {"type": "text", "content": text}
                return None
            
            elif event_type == "response.thinking.delta":
                # Agent's internal reasoning - goes to thinking panel, NOT main content
                text = data.get("text", "")
                if text:
                    return {
                        "type": "thinking",
                        "title": "Reasoning",
                        "content": text
                    }
                return None
            
            elif event_type == "response.status":
                # Status updates - show as thinking steps
                status = data.get("status", "")
                message = data.get("message", "")
                
                status_titles = {
                    "planning": "Planning analysis approach",
                    "reasoning_agent_start": "Starting analysis",
                    "reasoning_agent_stop": "Analysis complete",
                    "reevaluating_plan": "Refining approach",
                    "streaming_analyst_results": "Running SQL query",
                }
                
                title = status_titles.get(status, message or status)
                if title:
                    return {
                        "type": "status",
                        "title": title,
                        "status": status
                    }
                return None
            
            elif event_type == "response.tool_result.status":
                # Tool execution status
                status = data.get("status", "")
                message = data.get("message", "")
                
                return {
                    "type": "tool_status",
                    "title": message or status,
                    "status": status
                }
            
            elif event_type == "response.tool_result":
                # Tool result - could contain SQL, data, or errors
                content = data.get("content", [])
                
                result = {"type": "tool_result"}
                
                if isinstance(content, list):
                    for item in content:
                        if isinstance(item, dict):
                            if "json" in item:
                                json_data = item["json"]
                                if "sql" in json_data:
                                    result["sql"] = json_data["sql"]
                                if "error" in json_data:
                                    result["error"] = json_data["error"].get("message", str(json_data["error"]))
                                if "data" in json_data:
                                    result["data"] = json_data["data"]
                            if "text" in item:
                                result["content"] = item["text"]
                
                return result if len(result) > 1 else None
            
            elif event_type == "response.chart":
                # Chart/visualization generated by the agent
                chart_spec = data.get("chart_spec", {})
                logger.info(f"Chart event received - chart_spec type: {type(chart_spec)}")
                
                # chart_spec may be a JSON string - parse it if so
                if isinstance(chart_spec, str):
                    try:
                        chart_spec = json.loads(chart_spec)
                        logger.info(f"Parsed chart spec, keys: {list(chart_spec.keys()) if isinstance(chart_spec, dict) else 'not dict'}")
                    except json.JSONDecodeError as e:
                        logger.error(f"Failed to parse chart_spec JSON: {e}")
                        return None
                
                if chart_spec and isinstance(chart_spec, dict):
                    return {
                        "type": "chart",
                        "chart_spec": chart_spec
                    }
                return None
            
            elif event_type == "response.done":
                return {"type": "done"}

            # Final assembled text (with annotations / citations)
            elif event_type == "response.text":
                annotations = data.get("annotations", []) or []
                citations = []
                for a in annotations:
                    citations.append({
                        "doc_id":    a.get("doc_id"),
                        "doc_title": a.get("doc_title"),
                        "text":      (a.get("text") or "")[:400],
                    })
                if citations:
                    return {"type": "citations", "citations": citations}
                return None

            # Follow-up question suggestions
            elif event_type == "response.suggested_queries":
                qs = data.get("suggested_queries", []) or []
                queries = [q.get("query") for q in qs if isinstance(q, dict) and q.get("query")]
                if queries:
                    return {"type": "suggested_queries", "queries": queries}
                return None

            # Tool invocation announcement (which tool the agent picked)
            elif event_type == "response.tool_use":
                return {
                    "type":  "tool_use",
                    "name":  data.get("name"),
                    "tool_use_id": data.get("tool_use_id"),
                }
            
            # Handle response.content.delta (alternative output format)
            elif event_type == "response.content.delta":
                text = data.get("text", "")
                if text:
                    return {"type": "text", "content": text}
                # Check for nested content
                content = data.get("content", [])
                if isinstance(content, list):
                    texts = [c.get("text", "") for c in content if isinstance(c, dict)]
                    if texts:
                        return {"type": "text", "content": "".join(texts)}
                return None
            
            # Log unknown event types for debugging
            logger.info(f"SSE UNKNOWN: type={event_type}, keys={list(data.keys())}")
            return None
            
        except Exception as e:
            logger.warning(f"Failed to parse SSE event: {e}")
            return None
    
    async def run_agent(
        self,
        message: str,
        conversation_history: Optional[List[Dict[str, str]]] = None
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Convenience method to run agent with a single message.
        
        Args:
            message: User's message/question
            conversation_history: Optional previous messages
            
        Yields:
            Event dicts from the agent stream
        """
        messages = conversation_history or []
        messages.append({"role": "user", "content": message})
        
        async for event in self.run_agent_stream(messages):
            yield event


# Singleton instance
_agent_client: Optional[CortexAgentClient] = None


def get_cortex_agent_client() -> CortexAgentClient:
    """Get or create Cortex Agent client singleton."""
    global _agent_client
    if _agent_client is None:
        _agent_client = CortexAgentClient()
    return _agent_client
