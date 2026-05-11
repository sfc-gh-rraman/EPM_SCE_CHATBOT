"""
SCE EPM Contract Chatbot - Snowflake Service (SPCS Compatible)
Uses Snowpark Session for SPCS (auto-detects environment).
Falls back to CLI for local development.
Includes auto-reconnection on token expiration.
"""

import json
import os
import subprocess
from typing import Any, Dict, List, Optional
import logging

logger = logging.getLogger(__name__)


def _detect_spcs() -> bool:
    """Detect if running inside SPCS container"""
    if os.path.exists("/snowflake/session/token"):
        return True
    if os.environ.get("SNOWFLAKE_HOST"):
        return True
    if not os.path.exists(os.path.expanduser("~/Library/Python/3.11/bin/snow")):
        if os.path.exists("/app"):
            return True
    return False


IS_SPCS = _detect_spcs()


class SnowflakeServiceSPCS:
    """
    Service for interacting with Snowflake.
    Automatically detects SPCS environment and uses appropriate connection method.
    Includes auto-reconnection on token expiration.
    """
    
    def __init__(self, connection_name: str = "demo"):
        self.connection_name = connection_name
        self.database = os.environ.get("SNOWFLAKE_DATABASE", "SCE_EPM_DB")
        self.schema = os.environ.get("SNOWFLAKE_SCHEMA", "ATOMIC")
        self._session = None
        self._connection = None
        
        self.is_spcs = IS_SPCS
        
        if self.is_spcs:
            logger.info("Running inside SPCS - using Snowpark Session")
            self._init_snowpark_session()
        else:
            logger.info("Running locally - using Snowflake CLI")
            self.snow_path = self._find_snow_cli()
    
    def _find_snow_cli(self) -> str:
        """Find the snow CLI path"""
        possible_paths = [
            os.path.expanduser("~/Library/Python/3.11/bin/snow"),
            os.path.expanduser("~/.local/bin/snow"),
            os.path.expanduser("~/.snowflake/bin/snow"),
            "/usr/local/bin/snow",
            "snow"
        ]
        for path in possible_paths:
            if os.path.exists(path) or path == "snow":
                return path
        return "snow"
    
    def _init_snowpark_session(self):
        """Initialize Snowpark Session for SPCS environment"""
        try:
            from snowflake.snowpark import Session
            
            print(f"[SPCS] Initializing Snowpark Session...", flush=True)
            
            self._session = Session.builder.getOrCreate()
            
            print(f"[SPCS] Session created, setting database/schema...", flush=True)
            
            self._session.sql(f"USE DATABASE {self.database}").collect()
            self._session.sql(f"USE SCHEMA {self.schema}").collect()
            
            print(f"[SPCS] Snowpark Session established - DB: {self.database}, Schema: {self.schema}", flush=True)
            logger.info(f"Snowpark Session established - DB: {self.database}, Schema: {self.schema}")
            
            # Test query
            test_result = self._session.sql("SELECT COUNT(*) as cnt FROM CONTRACT").collect()
            print(f"[SPCS] Test query result: {test_result}", flush=True)
            
        except Exception as e:
            import traceback
            print(f"[SPCS] Failed to establish Snowpark Session: {e}", flush=True)
            traceback.print_exc()
            logger.error(f"Failed to establish Snowpark Session: {e}")
            self._init_connector_fallback()
    
    def _init_connector_fallback(self):
        """Fallback to connector if Snowpark fails - also used for reconnection"""
        try:
            import snowflake.connector
            
            if self._connection:
                try:
                    self._connection.close()
                except:
                    pass
                self._connection = None
            
            token_path = "/snowflake/session/token"
            token = ""
            if os.path.exists(token_path):
                with open(token_path, "r") as f:
                    token = f.read().strip()
            
            warehouse = os.environ.get("SNOWFLAKE_WAREHOUSE", "SCE_EPM_WH")
            
            self._connection = snowflake.connector.connect(
                host=os.environ.get("SNOWFLAKE_HOST", ""),
                account=os.environ.get("SNOWFLAKE_ACCOUNT", ""),
                authenticator="oauth",
                token=token,
                database=self.database,
                schema=self.schema,
                warehouse=warehouse
            )
            print(f"[SPCS] Connector established with warehouse: {warehouse}", flush=True)
            logger.info(f"Connector fallback connection established with warehouse: {warehouse}")
            return True
        except Exception as e:
            print(f"[SPCS] Connector fallback failed: {e}", flush=True)
            logger.error(f"Connector fallback also failed: {e}")
            return False
    
    def _reconnect_if_needed(self, error_msg: str) -> bool:
        """Check if error is token expiration and reconnect if so"""
        error_str = str(error_msg).lower()
        if "390114" in str(error_msg) or ("token" in error_str and "expired" in error_str):
            print(f"[SPCS] Token expired, reconnecting...", flush=True)
            return self._init_connector_fallback()
        return False
    
    def execute_query(self, query: str) -> List[Dict[str, Any]]:
        """Execute a SQL query and return results as list of dicts"""
        if self.is_spcs:
            return self._execute_query_snowpark(query)
        else:
            return self._execute_query_cli(query)
    
    def _execute_query_snowpark(self, query: str, retry: bool = True) -> List[Dict[str, Any]]:
        """Execute query using Snowpark Session (SPCS) with auto-reconnect on token expiration"""
        print(f"[QUERY] Executing: {query[:200]}...", flush=True)
        
        try:
            if self._session:
                print(f"[QUERY] Using Snowpark Session", flush=True)
                df = self._session.sql(query)
                rows = df.collect()
                if not rows:
                    print(f"[QUERY] No rows returned", flush=True)
                    return []
                
                results = []
                for row in rows:
                    row_dict = row.asDict()
                    for key, value in row_dict.items():
                        if hasattr(value, 'isoformat'):
                            row_dict[key] = value.isoformat()
                    results.append(row_dict)
                
                print(f"[QUERY] Returned {len(results)} rows", flush=True)
                return results
            elif self._connection:
                print(f"[QUERY] Using Connector fallback", flush=True)
                cursor = self._connection.cursor()
                cursor.execute(query)
                columns = [desc[0] for desc in cursor.description] if cursor.description else []
                rows = cursor.fetchall()
                
                print(f"[QUERY] Fetched {len(rows)} rows, columns: {columns[:5]}...", flush=True)
                
                results = []
                for row in rows:
                    row_dict = {}
                    for i, col in enumerate(columns):
                        value = row[i]
                        if hasattr(value, 'isoformat'):
                            value = value.isoformat()
                        row_dict[col] = value
                    results.append(row_dict)
                
                cursor.close()
                print(f"[QUERY] Returning {len(results)} results", flush=True)
                return results
            else:
                print(f"[QUERY] ERROR: No connection available!", flush=True)
                logger.error("No SPCS connection available")
                return []
                
        except Exception as e:
            error_str = str(e)
            print(f"[QUERY] EXCEPTION: {error_str}", flush=True)
            logger.error(f"SPCS query failed: {e}")
            
            # Check if token expired and retry once
            if retry and self._reconnect_if_needed(error_str):
                print(f"[QUERY] Retrying after reconnect...", flush=True)
                return self._execute_query_snowpark(query, retry=False)
            
            return []
    
    def _execute_query_cli(self, query: str) -> List[Dict[str, Any]]:
        """Execute query using Snowflake CLI (local development)"""
        try:
            cmd = [
                self.snow_path, "sql", 
                "-c", self.connection_name,
                "--format", "JSON",
                "-q", query
            ]
            
            result = subprocess.run(
                cmd, 
                capture_output=True, 
                text=True, 
                timeout=120
            )
            
            if result.returncode != 0:
                logger.error(f"Query failed: {result.stderr}")
                return []
            
            return self._parse_json_output(result.stdout)
            
        except subprocess.TimeoutExpired:
            logger.error("Query timeout")
            return []
        except Exception as e:
            logger.error(f"CLI query failed: {e}")
            return []
    
    def _parse_json_output(self, output: str) -> List[Dict[str, Any]]:
        """Parse snow sql JSON output into list of dicts"""
        try:
            lines = output.strip().split('\n')
            json_lines = []
            in_json = False
            
            for line in lines:
                stripped = line.strip()
                if stripped.startswith('['):
                    in_json = True
                if in_json:
                    json_lines.append(line)
                if in_json and stripped.endswith(']'):
                    break
            
            if not json_lines:
                return []
            
            json_str = '\n'.join(json_lines)
            return json.loads(json_str)
            
        except json.JSONDecodeError as e:
            logger.error(f"JSON parse error: {e}")
            return []
    
    # =========================================================================
    # Project Queries
    # =========================================================================
    
    def get_projects(self) -> List[Dict[str, Any]]:
        """Get all projects."""
        sql = f"""
        SELECT 
            PROJECT_ID,
            PROJECT_NAME,
            PROJECT_TYPE,
            STATUS,
            CITY,
            STATE,
            LATITUDE,
            LONGITUDE,
            ORIGINAL_BUDGET,
            CURRENT_BUDGET,
            CONTINGENCY_BUDGET,
            CONTINGENCY_USED,
            CPI,
            SPI,
            PRIME_CONTRACTOR
        FROM {self.database}.{self.schema}.PROJECT
        ORDER BY PROJECT_NAME
        """
        return self.execute_query(sql)
    
    def get_project_detail(self, project_id: str) -> Optional[Dict[str, Any]]:
        """Get detailed project information."""
        sql = f"""
        SELECT *
        FROM {self.database}.{self.schema}.PROJECT
        WHERE PROJECT_ID = '{project_id}'
        """
        results = self.execute_query(sql)
        return results[0] if results else None
    
    def get_portfolio_summary(self) -> Dict[str, Any]:
        """Get portfolio-level KPIs."""
        sql = f"""
        SELECT 
            COUNT(*) AS TOTAL_PROJECTS,
            ROUND(SUM(ORIGINAL_BUDGET), 0) AS TOTAL_BUDGET,
            ROUND(SUM(CURRENT_BUDGET), 0) AS CURRENT_BUDGET,
            ROUND(SUM(CONTINGENCY_BUDGET), 0) AS TOTAL_CONTINGENCY,
            ROUND(SUM(CONTINGENCY_USED), 0) AS CONTINGENCY_USED,
            ROUND(AVG(CPI), 3) AS AVG_CPI,
            ROUND(AVG(SPI), 3) AS AVG_SPI,
            SUM(CASE WHEN CPI < 0.95 THEN 1 ELSE 0 END) AS PROJECTS_OVER_BUDGET,
            SUM(CASE WHEN SPI < 0.95 THEN 1 ELSE 0 END) AS PROJECTS_BEHIND_SCHEDULE
        FROM {self.database}.{self.schema}.PROJECT
        """
        results = self.execute_query(sql)
        return results[0] if results else {}
    
    # =========================================================================
    # Change Order Queries
    # =========================================================================
    
    def get_change_orders(self, project_id: Optional[str] = None, limit: int = 100) -> List[Dict[str, Any]]:
        """Get change orders with optional project filter."""
        where_clause = f"WHERE co.PROJECT_ID = '{project_id}'" if project_id else ""
        
        sql = f"""
        SELECT 
            co.CO_ID,
            co.PROJECT_ID,
            p.PROJECT_NAME,
            co.VENDOR_ID,
            v.VENDOR_NAME,
            co.CO_NUMBER,
            co.CO_TITLE,
            co.REASON_TEXT,
            co.APPROVED_AMOUNT,
            co.STATUS,
            co.ML_CATEGORY,
            co.ML_CONFIDENCE
        FROM {self.database}.{self.schema}.CHANGE_ORDER co
        JOIN {self.database}.{self.schema}.PROJECT p ON co.PROJECT_ID = p.PROJECT_ID
        LEFT JOIN {self.database}.{self.schema}.VENDOR v ON co.VENDOR_ID = v.VENDOR_ID
        {where_clause}
        ORDER BY co.APPROVED_AMOUNT DESC
        LIMIT {limit}
        """
        return self.execute_query(sql)
    
    # =========================================================================
    # Schedule Activity Queries
    # =========================================================================
    
    def get_activities(self, project_id: Optional[str] = None, critical_only: bool = False) -> List[Dict[str, Any]]:
        """Get schedule activities with optional filters."""
        where_clauses = []
        if project_id:
            where_clauses.append(f"sa.PROJECT_ID = '{project_id}'")
        if critical_only:
            where_clauses.append("sa.SLIP_PROBABILITY > 0.7")
        
        where_clause = "WHERE " + " AND ".join(where_clauses) if where_clauses else ""
        
        sql = f"""
        SELECT 
            sa.ACTIVITY_ID,
            sa.PROJECT_ID,
            p.PROJECT_NAME,
            sa.ACTIVITY_NAME,
            sa.PLANNED_START,
            sa.PLANNED_FINISH,
            sa.FORECAST_FINISH,
            sa.PERCENT_COMPLETE,
            sa.SLIP_PROBABILITY
        FROM {self.database}.{self.schema}.SCHEDULE_ACTIVITY sa
        JOIN {self.database}.{self.schema}.PROJECT p ON sa.PROJECT_ID = p.PROJECT_ID
        {where_clause}
        ORDER BY sa.SLIP_PROBABILITY DESC
        LIMIT 100
        """
        return self.execute_query(sql)
    
    def get_at_risk_activities(self, threshold: float = 0.5) -> List[Dict[str, Any]]:
        """Get activities with slip probability above threshold."""
        sql = f"""
        SELECT 
            sa.ACTIVITY_ID,
            sa.PROJECT_ID,
            p.PROJECT_NAME,
            sa.ACTIVITY_NAME,
            sa.PLANNED_FINISH,
            sa.FORECAST_FINISH,
            sa.PERCENT_COMPLETE,
            sa.SLIP_PROBABILITY,
            DATEDIFF('day', sa.PLANNED_FINISH, sa.FORECAST_FINISH) as SLIP_DAYS
        FROM {self.database}.{self.schema}.SCHEDULE_ACTIVITY sa
        JOIN {self.database}.{self.schema}.PROJECT p ON sa.PROJECT_ID = p.PROJECT_ID
        WHERE sa.SLIP_PROBABILITY > {threshold}
        ORDER BY sa.SLIP_PROBABILITY DESC
        LIMIT 50
        """
        return self.execute_query(sql)
    
    def search_change_orders(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        """
        Search change orders using semantic LIKE matching.
        In production, this would use Cortex Search, but for reliability
        we use SQL LIKE with keyword extraction.
        """
        logger.info(f"Searching change orders: {query[:50]}...")
        
        # Extract keywords from query
        keywords = [word.strip().lower() for word in query.split() if len(word.strip()) > 2]
        
        if not keywords:
            return []
        
        # Build LIKE conditions for each keyword
        like_conditions = []
        for kw in keywords[:5]:  # Limit to 5 keywords
            like_conditions.append(f"LOWER(co.REASON_TEXT) LIKE '%{kw}%'")
        
        # Combine with OR for broader matches
        where_clause = " OR ".join(like_conditions)
        
        sql = f"""
        SELECT 
            co.CO_ID,
            co.PROJECT_ID,
            p.PROJECT_NAME,
            co.VENDOR_ID,
            v.VENDOR_NAME,
            co.CO_NUMBER,
            co.CO_TITLE,
            co.REASON_TEXT,
            co.APPROVED_AMOUNT,
            co.ML_CATEGORY,
            co.APPROVAL_DATE
        FROM {self.database}.{self.schema}.CHANGE_ORDER co
        JOIN {self.database}.{self.schema}.PROJECT p ON co.PROJECT_ID = p.PROJECT_ID
        LEFT JOIN {self.database}.{self.schema}.VENDOR v ON co.VENDOR_ID = v.VENDOR_ID
        WHERE ({where_clause})
          AND co.STATUS = 'APPROVED'
        ORDER BY co.APPROVAL_DATE DESC
        LIMIT {limit}
        """
        
        try:
            results = self.execute_query(sql)
            logger.info(f"Search found {len(results)} results")
            return results
        except Exception as e:
            logger.error(f"Search failed: {e}")
            return []
    
    def get_grounding_pattern(self) -> Dict[str, Any]:
        """Get the grounding pattern - THE WOW MOMENT."""
        sql = f"""
        SELECT 
            co.CO_ID,
            co.PROJECT_ID,
            p.PROJECT_NAME,
            v.VENDOR_NAME,
            co.REASON_TEXT,
            co.APPROVED_AMOUNT,
            co.ML_CATEGORY,
            co.ML_CONFIDENCE
        FROM {self.database}.{self.schema}.CHANGE_ORDER co
        JOIN {self.database}.{self.schema}.PROJECT p ON co.PROJECT_ID = p.PROJECT_ID
        LEFT JOIN {self.database}.{self.schema}.VENDOR v ON co.VENDOR_ID = v.VENDOR_ID
        WHERE LOWER(co.REASON_TEXT) LIKE '%ground%'
          AND co.STATUS = 'APPROVED'
        ORDER BY p.PROJECT_NAME
        """
        results = self.execute_query(sql)
        
        if results:
            total_amount = sum(r.get("APPROVED_AMOUNT", 0) or 0 for r in results)
            project_count = len(set(r.get("PROJECT_ID") for r in results))
            avg_amount = total_amount / len(results) if results else 0
            return {
                "pattern_name": "Missing Grounding Specifications",
                "co_count": len(results),
                "project_count": project_count,
                "total_amount": total_amount,
                "avg_amount": avg_amount,
                "common_vendor": results[0].get("VENDOR_NAME") if results else None,
                "change_orders": results
            }
        return {}
    
    def get_scope_gap_analysis(self) -> Dict[str, Any]:
        """Analyze scope gaps across all change orders."""
        sql = f"""
        SELECT 
            ML_CATEGORY,
            COUNT(*) as CO_COUNT,
            ROUND(SUM(APPROVED_AMOUNT), 2) as TOTAL_AMOUNT,
            ROUND(AVG(APPROVED_AMOUNT), 2) as AVG_AMOUNT,
            COUNT(DISTINCT PROJECT_ID) as PROJECT_COUNT
        FROM {self.database}.{self.schema}.CHANGE_ORDER
        WHERE STATUS = 'APPROVED'
        GROUP BY ML_CATEGORY
        ORDER BY TOTAL_AMOUNT DESC
        """
        results = self.execute_query(sql)
        
        # Also get projects with scope issues
        project_sql = f"""
        SELECT 
            p.PROJECT_ID,
            p.PROJECT_NAME,
            COUNT(co.CO_ID) as CO_COUNT,
            ROUND(SUM(co.APPROVED_AMOUNT), 2) as TOTAL_CO_AMOUNT
        FROM {self.database}.{self.schema}.PROJECT p
        JOIN {self.database}.{self.schema}.CHANGE_ORDER co ON p.PROJECT_ID = co.PROJECT_ID
        WHERE co.STATUS = 'APPROVED'
        GROUP BY p.PROJECT_ID, p.PROJECT_NAME
        HAVING COUNT(co.CO_ID) > 5
        ORDER BY TOTAL_CO_AMOUNT DESC
        """
        project_results = self.execute_query(project_sql)
        
        return {
            "by_category": results,
            "high_co_projects": project_results,
            "total_categories": len(results),
            "total_high_co_projects": len(project_results)
        }
    
    # =========================================================================
    # Vendor Queries
    # =========================================================================
    
    def get_vendors(self) -> List[Dict[str, Any]]:
        """Get all vendors with risk scores."""
        sql = f"""
        SELECT 
            VENDOR_ID,
            VENDOR_NAME,
            TRADE_CATEGORY,
            VENDOR_TYPE,
            AVG_CO_RATE,
            ONTIME_DELIVERY_RATE,
            QUALITY_SCORE,
            RISK_SCORE
        FROM {self.database}.{self.schema}.VENDOR
        WHERE ACTIVE_FLAG = TRUE
        ORDER BY RISK_SCORE DESC
        """
        return self.execute_query(sql)
    
    # =========================================================================
    # Direct SQL Query - Pattern Matching (RELIABLE)
    # =========================================================================
    
    def direct_sql_query(self, question: str) -> Dict[str, Any]:
        """Handle common questions with direct SQL - RELIABLE approach."""
        question_lower = question.lower()
        sql = None
        explanation = ""
        db = self.database
        schema = self.schema
        
        # Project listing
        if any(kw in question_lower for kw in ["list", "name", "what are", "show me", "give me"]) and "project" in question_lower:
            sql = f"""
                SELECT PROJECT_NAME, PROJECT_TYPE, CITY, STATE, 
                       ROUND(ORIGINAL_BUDGET/1000000, 1) as BUDGET_M, 
                       ROUND(CPI, 3) as CPI, ROUND(SPI, 3) as SPI, STATUS
                FROM {db}.{schema}.PROJECT 
                ORDER BY PROJECT_NAME
            """
            explanation = "Listing all projects with key metrics"
        
        # Project count
        elif "how many" in question_lower and "project" in question_lower:
            sql = f"SELECT COUNT(*) as PROJECT_COUNT FROM {db}.{schema}.PROJECT"
            explanation = "Counting total projects"
        
        # Portfolio summary
        elif any(kw in question_lower for kw in ["summary", "overview", "portfolio", "total budget"]):
            sql = f"""
                SELECT 
                    COUNT(*) as TOTAL_PROJECTS,
                    ROUND(SUM(ORIGINAL_BUDGET)/1000000000, 2) as TOTAL_BUDGET_B,
                    ROUND(AVG(CPI), 3) as AVG_CPI,
                    ROUND(AVG(SPI), 3) as AVG_SPI,
                    SUM(CASE WHEN CPI < 0.95 THEN 1 ELSE 0 END) as OVER_BUDGET_COUNT,
                    SUM(CASE WHEN SPI < 0.95 THEN 1 ELSE 0 END) as BEHIND_SCHEDULE_COUNT
                FROM {db}.{schema}.PROJECT
            """
            explanation = "Portfolio summary with key metrics"
        
        # Projects over budget
        elif ("over budget" in question_lower) or ("cpi" in question_lower and any(kw in question_lower for kw in ["below", "under", "low", "less"])):
            sql = f"""
                SELECT PROJECT_NAME, ROUND(CPI, 3) as CPI, ROUND(SPI, 3) as SPI,
                       ROUND(ORIGINAL_BUDGET/1000000, 1) as BUDGET_M
                FROM {db}.{schema}.PROJECT 
                WHERE CPI < 0.95 
                ORDER BY CPI ASC
            """
            explanation = "Projects with CPI below 0.95 (over budget)"
        
        # Projects behind schedule
        elif "behind schedule" in question_lower or ("spi" in question_lower and any(kw in question_lower for kw in ["below", "under", "low", "less"])):
            sql = f"""
                SELECT PROJECT_NAME, ROUND(SPI, 3) as SPI, ROUND(CPI, 3) as CPI,
                       ROUND(ORIGINAL_BUDGET/1000000, 1) as BUDGET_M
                FROM {db}.{schema}.PROJECT 
                WHERE SPI < 0.95 
                ORDER BY SPI ASC
            """
            explanation = "Projects with SPI below 0.95 (behind schedule)"
        
        # Vendor listing
        elif any(kw in question_lower for kw in ["list", "show", "what are"]) and "vendor" in question_lower:
            sql = f"""
                SELECT VENDOR_NAME, TRADE_CATEGORY, RISK_SCORE,
                       ROUND(ONTIME_DELIVERY_RATE * 100, 1) as ONTIME_PCT,
                       ROUND(QUALITY_SCORE, 1) as QUALITY
                FROM {db}.{schema}.VENDOR 
                WHERE ACTIVE_FLAG = TRUE
                ORDER BY RISK_SCORE DESC
            """
            explanation = "Listing all active vendors with risk scores"
        
        # Vendors with most change orders
        elif "vendor" in question_lower and ("most" in question_lower or "change order" in question_lower):
            sql = f"""
                SELECT v.VENDOR_NAME, v.TRADE_CATEGORY, COUNT(co.CO_ID) as CO_COUNT,
                       ROUND(SUM(co.APPROVED_AMOUNT)/1000, 1) as TOTAL_K
                FROM {db}.{schema}.VENDOR v
                LEFT JOIN {db}.{schema}.CHANGE_ORDER co ON v.VENDOR_ID = co.VENDOR_ID
                WHERE v.ACTIVE_FLAG = TRUE
                GROUP BY v.VENDOR_ID, v.VENDOR_NAME, v.TRADE_CATEGORY
                ORDER BY CO_COUNT DESC
                LIMIT 10
            """
            explanation = "Vendors ranked by number of change orders"
        
        # Change order count
        elif "how many" in question_lower and "change order" in question_lower:
            sql = f"SELECT COUNT(*) as CO_COUNT FROM {db}.{schema}.CHANGE_ORDER"
            explanation = "Total change order count"
        
        # Total spend by project
        elif ("spend" in question_lower or "budget" in question_lower) and "project" in question_lower:
            sql = f"""
                SELECT PROJECT_NAME, 
                       ROUND(ORIGINAL_BUDGET/1000000, 1) as ORIGINAL_BUDGET_M,
                       ROUND(CURRENT_BUDGET/1000000, 1) as CURRENT_BUDGET_M,
                       ROUND((CURRENT_BUDGET - ORIGINAL_BUDGET)/1000000, 2) as VARIANCE_M
                FROM {db}.{schema}.PROJECT
                ORDER BY ORIGINAL_BUDGET DESC
            """
            explanation = "Budget breakdown by project"
        
        # Change orders by category
        elif "change order" in question_lower and ("category" in question_lower or "type" in question_lower or "breakdown" in question_lower):
            sql = f"""
                SELECT ML_CATEGORY, COUNT(*) as CO_COUNT, 
                       ROUND(SUM(APPROVED_AMOUNT)/1000, 1) as TOTAL_K,
                       ROUND(AVG(ML_CONFIDENCE), 2) as AVG_CONFIDENCE
                FROM {db}.{schema}.CHANGE_ORDER
                WHERE ML_CATEGORY IS NOT NULL
                GROUP BY ML_CATEGORY
                ORDER BY CO_COUNT DESC
            """
            explanation = "Change orders grouped by ML classification"
        
        if sql:
            try:
                results = self.execute_query(sql)
                return {
                    "sql": sql.strip(),
                    "results": results,
                    "explanation": explanation,
                    "error": None
                }
            except Exception as e:
                logger.error(f"Direct SQL query failed: {e}")
                return {"error": str(e), "sql": sql, "results": []}
        
        return {"error": "Could not understand the question", "sql": None, "results": []}
    
    # =========================================================================
    # Cortex LLM
    # =========================================================================
    
    def cortex_complete(self, prompt: str, model: str = "mistral-large2") -> str:
        """Call Cortex Complete for LLM generation."""
        escaped_prompt = prompt.replace("'", "''").replace("\\", "\\\\")
        
        sql = f"""
        SELECT SNOWFLAKE.CORTEX.COMPLETE(
            '{model}',
            '{escaped_prompt}'
        ) AS RESPONSE
        """
        
        print(f"[LLM] Calling Cortex LLM with model: {model}", flush=True)
        
        try:
            if self.is_spcs and self._connection:
                cursor = self._connection.cursor()
                cursor.execute(sql)
                row = cursor.fetchone()
                cursor.close()
                
                if row and row[0]:
                    return str(row[0])
                return ""
            elif self.is_spcs and self._session:
                df = self._session.sql(sql)
                rows = df.collect()
                if rows and rows[0][0]:
                    return str(rows[0][0])
                return ""
            else:
                return self._call_llm_cli(sql)
        except Exception as e:
            print(f"[LLM] Error: {e}", flush=True)
            logger.error(f"LLM call failed: {e}")
            return ""
    
    def _call_llm_cli(self, sql: str) -> str:
        """Call Cortex LLM using CLI"""
        try:
            cmd = [self.snow_path, "sql", "-c", self.connection_name, "-q", sql]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            
            if result.returncode != 0:
                return ""
            
            output = result.stdout
            lines = output.strip().split('\n')
            
            for i, line in enumerate(lines):
                if 'RESPONSE' in line and i + 2 < len(lines):
                    for j in range(i + 1, len(lines)):
                        if lines[j].startswith('|') and not lines[j].startswith('|--'):
                            response = lines[j].strip('| ')
                            return response
            return ""
        except Exception as e:
            logger.error(f"LLM call failed: {e}")
            return ""
    
    def cortex_analyst(self, question: str) -> Dict[str, Any]:
        """Text-to-SQL using Cortex Complete LLM as fallback."""
        schema_context = f"""
You are a SQL expert. Generate Snowflake SQL to answer the user's question.

DATABASE: {self.database}
SCHEMA: {self.schema}

TABLES:
1. PROJECT (PROJECT_ID, PROJECT_NAME, PROJECT_CODE, PROJECT_TYPE, STATUS, CITY, STATE, 
   LATITUDE, LONGITUDE, PLANNED_START_DATE, PLANNED_END_DATE, ACTUAL_START_DATE, ACTUAL_END_DATE,
   ORIGINAL_BUDGET, CURRENT_BUDGET, CONTINGENCY_BUDGET, CONTINGENCY_USED, CPI, SPI,
   PROGRAM_ID, OWNER_NAME, PRIME_CONTRACTOR)

2. CHANGE_ORDER (CO_ID, PROJECT_ID, VENDOR_ID, CO_NUMBER, CO_TITLE, CO_TYPE, CO_CATEGORY,
   COST_CODE, ORIGINAL_AMOUNT, APPROVED_AMOUNT, STATUS, APPROVAL_LEVEL, SUBMIT_DATE,
   APPROVAL_DATE, EFFECTIVE_DATE, REASON_TEXT, JUSTIFICATION, ML_CATEGORY, ML_CONFIDENCE)

3. VENDOR (VENDOR_ID, VENDOR_NAME, TRADE_CATEGORY, VENDOR_TYPE, AVG_CO_RATE, 
   ONTIME_DELIVERY_RATE, QUALITY_SCORE, RISK_SCORE, ACTIVE_FLAG)

RULES:
- Use {self.database}.{self.schema}.TABLE_NAME for all tables
- For money values, use ROUND(column/1000000, 2) for millions
- Return ONLY valid SQL, no explanations
- Always include ORDER BY and LIMIT 20
"""
        
        prompt = f"{schema_context}\n\nUSER QUESTION: {question}\n\nSQL:"
        
        try:
            generated_sql = self.cortex_complete(prompt)
            
            if not generated_sql:
                return {"answer": None, "sql": None, "data": None, "error": "LLM did not generate SQL"}
            
            # Clean up SQL
            generated_sql = generated_sql.strip()
            if generated_sql.startswith("```"):
                lines = generated_sql.split("\n")
                generated_sql = "\n".join(lines[1:-1] if lines[-1] == "```" else lines[1:])
            generated_sql = generated_sql.strip()
            
            # Execute
            results = self.execute_query(generated_sql)
            return {"answer": "Query executed", "sql": generated_sql, "data": results, "error": None}
        except Exception as e:
            return {"answer": None, "sql": None, "data": None, "error": str(e)}
    
    def close(self):
        """Close the connection"""
        if self._session:
            self._session.close()
        if self._connection:
            try:
                self._connection.close()
            except:
                pass


# Singleton instance
_snowflake_service: Optional[SnowflakeServiceSPCS] = None


def get_snowflake_service() -> SnowflakeServiceSPCS:
    """Get or create Snowflake service singleton"""
    global _snowflake_service
    if _snowflake_service is None:
        _snowflake_service = SnowflakeServiceSPCS()
    return _snowflake_service
