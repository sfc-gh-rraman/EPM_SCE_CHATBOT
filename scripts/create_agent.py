"""Create the SCE EPM Contract Agent via the Snowflake Cortex Agents REST API."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import requests
import snowflake.connector

SPEC_PATH    = Path(__file__).parent.parent / "cortex" / "sce_epm_agent_spec.json"
DATABASE     = "SCE_EPM_DB"
SCHEMA       = "CORTEX"
AGENT_NAME   = "SCE_EPM_CONTRACT_AGENT"
CONNECTION   = sys.argv[1] if len(sys.argv) > 1 else "my_snowflake"

agent_spec = json.loads(SPEC_PATH.read_text())

print(f"Connecting via '{CONNECTION}'...")
conn = snowflake.connector.connect(connection_name=CONNECTION)
try:
    host    = conn.host.replace("_", "-")
    token   = conn.rest.token
    base    = f"https://{host}"
    url_col = f"{base}/api/v2/databases/{DATABASE}/schemas/{SCHEMA}/agents"
    url_one = f"{url_col}/{AGENT_NAME}"
    headers = {
        "Authorization":              f"Bearer {token}",
        "Content-Type":               "application/json",
        "Accept":                     "application/json",
        "X-Snowflake-Authorization-Token-Type": "KEYPAIR_JWT",
    }

    body = {
        "name":          AGENT_NAME,
        "comment":       "SCE EPM contract intelligence agent (analyst + search + custom tools).",
        "agent_spec":    agent_spec,
    }

    # Try create
    print(f"POST {url_col}")
    r = requests.post(url_col, headers=headers, json=body, timeout=30)
    print(f"  status: {r.status_code}")
    print(f"  body:   {r.text[:600]}")

    if r.status_code in (409, 400):
        # already exists or alter — try PUT
        print(f"PUT {url_one}")
        r = requests.put(url_one, headers=headers, json=body, timeout=30)
        print(f"  status: {r.status_code}")
        print(f"  body:   {r.text[:600]}")

    if not r.ok:
        sys.exit(1)
    print(f"\n✓ Agent {DATABASE}.{SCHEMA}.{AGENT_NAME} ready.")
finally:
    conn.close()
