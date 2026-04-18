"""
SNBAWS MCP Server for ServiceNow
Custom-built MCP server that exposes ServiceNow operations as tools for Claude Code.
Supports both Basic Auth (PDI) and OAuth (company instances).

Usage:
    python mcp-server/server.py

Configure in .claude/mcp.json to auto-start with Claude Code.
"""

import os
import json
import base64
from typing import Optional
from mcp.server.fastmcp import FastMCP
import httpx

# --- Configuration ---

def load_env():
    """Load .env file from project root."""
    env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")
    if os.path.exists(env_path):
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    os.environ.setdefault(key.strip(), value.strip())

load_env()

SN_INSTANCE = os.environ.get("SN_INSTANCE_URL", "").rstrip("/")
SN_USERNAME = os.environ.get("SN_USERNAME", "")
SN_PASSWORD = os.environ.get("SN_PASSWORD", "")

# --- MCP Server ---

mcp = FastMCP(
    "snbaws-servicenow",
    instructions="""ServiceNow MCP Server for the SNBAWS project.
    Provides tools to query, create, update, and delete records on any ServiceNow table.
    Includes specialized tools for Service Portal widgets, script artifacts, and CSM operations.""",
)


def _auth_headers() -> dict:
    """Build authentication headers for SN REST API."""
    token = base64.b64encode(f"{SN_USERNAME}:{SN_PASSWORD}".encode()).decode()
    return {
        "Authorization": f"Basic {token}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


def _table_url(table: str, sys_id: str = "") -> str:
    """Build the Table API URL."""
    url = f"{SN_INSTANCE}/api/now/table/{table}"
    if sys_id:
        url += f"/{sys_id}"
    return url


# --- Core Table Operations ---

@mcp.tool()
async def query_records(
    table: str,
    query: str = "",
    fields: str = "",
    limit: int = 10,
    offset: int = 0,
    order_by: str = "",
) -> str:
    """Query records from any ServiceNow table.

    Args:
        table: Table name (e.g., 'incident', 'sp_widget', 'sys_script_include')
        query: Encoded query string (e.g., 'active=true^priority=1')
        fields: Comma-separated field names to return (empty = all fields)
        limit: Maximum records to return (default 10)
        offset: Number of records to skip (for pagination)
        order_by: Field to order by (prefix with - for descending)
    """
    params = {"sysparm_limit": limit, "sysparm_offset": offset}
    if query:
        params["sysparm_query"] = query
    if fields:
        params["sysparm_fields"] = fields
    if order_by:
        params["sysparm_orderby"] = order_by

    async with httpx.AsyncClient(verify=False, timeout=30) as client:
        r = await client.get(_table_url(table), headers=_auth_headers(), params=params)
        return r.text


@mcp.tool()
async def get_record(table: str, sys_id: str, fields: str = "") -> str:
    """Get a single record by sys_id.

    Args:
        table: Table name
        sys_id: The sys_id of the record
        fields: Comma-separated field names to return (empty = all fields)
    """
    params = {}
    if fields:
        params["sysparm_fields"] = fields

    async with httpx.AsyncClient(verify=False, timeout=30) as client:
        r = await client.get(
            _table_url(table, sys_id), headers=_auth_headers(), params=params
        )
        return r.text


@mcp.tool()
async def create_record(table: str, data: str) -> str:
    """Create a new record on any ServiceNow table.

    Args:
        table: Table name (e.g., 'incident', 'sp_widget', 'sys_script_include')
        data: JSON string of field name/value pairs
    """
    async with httpx.AsyncClient(verify=False, timeout=30) as client:
        r = await client.post(
            _table_url(table), headers=_auth_headers(), content=data
        )
        return r.text


@mcp.tool()
async def update_record(table: str, sys_id: str, data: str) -> str:
    """Update an existing record via PUT.

    Args:
        table: Table name
        sys_id: The sys_id of the record to update
        data: JSON string of field name/value pairs to update
    """
    async with httpx.AsyncClient(verify=False, timeout=30) as client:
        r = await client.put(
            _table_url(table, sys_id), headers=_auth_headers(), content=data
        )
        return r.text


@mcp.tool()
async def delete_record(table: str, sys_id: str) -> str:
    """Delete a record by sys_id.

    Args:
        table: Table name
        sys_id: The sys_id of the record to delete
    """
    async with httpx.AsyncClient(verify=False, timeout=30) as client:
        r = await client.delete(
            _table_url(table, sys_id), headers=_auth_headers()
        )
        return f"HTTP {r.status_code}: {'Deleted' if r.status_code == 204 else r.text}"


# --- Script Artifact Operations ---

@mcp.tool()
async def get_script(table: str, name: str) -> str:
    """Get a script artifact by name. Returns the script content and metadata.

    Args:
        table: Script table (e.g., 'sys_script_include', 'sys_script', 'sys_ui_script', 'sys_script_client')
        name: Name of the script artifact
    """
    params = {
        "sysparm_query": f"name={name}",
        "sysparm_fields": "sys_id,name,script,active,api_name,description",
        "sysparm_limit": 1,
    }
    async with httpx.AsyncClient(verify=False, timeout=30) as client:
        r = await client.get(_table_url(table), headers=_auth_headers(), params=params)
        return r.text


@mcp.tool()
async def update_script(table: str, name: str, script: str) -> str:
    """Update the script content of a script artifact by name.

    Args:
        table: Script table (e.g., 'sys_script_include', 'sys_script', 'sys_ui_script')
        name: Name of the script artifact
        script: New script content
    """
    # First find the record
    params = {
        "sysparm_query": f"name={name}",
        "sysparm_fields": "sys_id,name",
        "sysparm_limit": 1,
    }
    async with httpx.AsyncClient(verify=False, timeout=30) as client:
        r = await client.get(_table_url(table), headers=_auth_headers(), params=params)
        result = r.json()
        records = result.get("result", [])
        if not records:
            return json.dumps({"error": f"No {table} record found with name '{name}'"})

        sys_id = records[0]["sys_id"]
        data = json.dumps({"script": script})
        r = await client.put(
            _table_url(table, sys_id), headers=_auth_headers(), content=data
        )
        return r.text


# --- Service Portal Operations ---

@mcp.tool()
async def list_widgets(query: str = "", limit: int = 20) -> str:
    """List Service Portal widgets.

    Args:
        query: Optional encoded query to filter widgets
        limit: Maximum widgets to return
    """
    params = {
        "sysparm_fields": "sys_id,name,id,category",
        "sysparm_limit": limit,
    }
    if query:
        params["sysparm_query"] = query

    async with httpx.AsyncClient(verify=False, timeout=30) as client:
        r = await client.get(
            _table_url("sp_widget"), headers=_auth_headers(), params=params
        )
        return r.text


@mcp.tool()
async def get_widget(widget_id: str) -> str:
    """Get a Service Portal widget by its widget ID (not sys_id).

    Args:
        widget_id: The widget ID (e.g., 'csm-unified-portal-header', 'snbaws-test-widget')
    """
    params = {
        "sysparm_query": f"id={widget_id}",
        "sysparm_fields": "sys_id,name,id,template,css,client_script,script,link,option_schema,description",
        "sysparm_limit": 1,
    }
    async with httpx.AsyncClient(verify=False, timeout=30) as client:
        r = await client.get(
            _table_url("sp_widget"), headers=_auth_headers(), params=params
        )
        return r.text


@mcp.tool()
async def create_widget(
    name: str,
    widget_id: str,
    css: str = "",
    client_script: str = "",
    server_script: str = "",
) -> str:
    """Create a new Service Portal widget. Note: HTML templates are sanitized by the REST API.
    Use sn-scriptsync for HTML template content.

    Args:
        name: Display name of the widget
        widget_id: URL-safe widget identifier (lowercase, hyphens)
        css: CSS/SCSS styles
        client_script: Client-side AngularJS controller
        server_script: Server-side script (wrapped in IIFE)
    """
    data = json.dumps({
        "name": name,
        "id": widget_id,
        "css": css,
        "client_script": client_script,
        "script": server_script,
    })
    async with httpx.AsyncClient(verify=False, timeout=30) as client:
        r = await client.post(
            _table_url("sp_widget"), headers=_auth_headers(), content=data
        )
        return r.text


# --- CSM Operations ---

@mcp.tool()
async def list_cases(query: str = "", limit: int = 10) -> str:
    """List CSM cases.

    Args:
        query: Optional encoded query (e.g., 'state=1^priority=2')
        limit: Maximum cases to return
    """
    params = {
        "sysparm_fields": "sys_id,number,short_description,state,priority,contact,account",
        "sysparm_limit": limit,
    }
    if query:
        params["sysparm_query"] = query

    async with httpx.AsyncClient(verify=False, timeout=30) as client:
        r = await client.get(
            _table_url("sn_customerservice_case"),
            headers=_auth_headers(),
            params=params,
        )
        return r.text


@mcp.tool()
async def list_orders(query: str = "", limit: int = 10) -> str:
    """List CSM orders.

    Args:
        query: Optional encoded query
        limit: Maximum orders to return
    """
    params = {
        "sysparm_fields": "sys_id,number,short_description,state,stage,account",
        "sysparm_limit": limit,
    }
    if query:
        params["sysparm_query"] = query

    async with httpx.AsyncClient(verify=False, timeout=30) as client:
        r = await client.get(
            _table_url("sn_csm_order"),
            headers=_auth_headers(),
            params=params,
        )
        return r.text


# --- Utility Operations ---

@mcp.tool()
async def test_connection() -> str:
    """Test the connection to the ServiceNow instance. Returns instance info."""
    async with httpx.AsyncClient(verify=False, timeout=15) as client:
        r = await client.get(
            _table_url("sys_properties"),
            headers=_auth_headers(),
            params={
                "sysparm_query": "name=glide.buildtag.last",
                "sysparm_fields": "name,value",
                "sysparm_limit": 1,
            },
        )
        result = r.json()
        records = result.get("result", [])
        build = records[0]["value"] if records else "unknown"
        return json.dumps({
            "status": "connected",
            "instance": SN_INSTANCE,
            "user": SN_USERNAME,
            "build": build,
            "http_status": r.status_code,
        })


@mcp.tool()
async def get_table_schema(table: str) -> str:
    """Get the schema (columns/fields) of a ServiceNow table.

    Args:
        table: Table name to get schema for
    """
    params = {
        "sysparm_query": f"name={table}",
        "sysparm_fields": "sys_id,label,name",
        "sysparm_limit": 1,
    }
    async with httpx.AsyncClient(verify=False, timeout=30) as client:
        # Get table record
        r = await client.get(
            _table_url("sys_db_object"), headers=_auth_headers(), params=params
        )
        table_result = r.json().get("result", [])
        if not table_result:
            return json.dumps({"error": f"Table '{table}' not found"})

        # Get columns
        r = await client.get(
            _table_url("sys_dictionary"),
            headers=_auth_headers(),
            params={
                "sysparm_query": f"name={table}^internal_type!=collection",
                "sysparm_fields": "element,column_label,internal_type,max_length,mandatory",
                "sysparm_limit": 100,
            },
        )
        return r.text


@mcp.tool()
async def run_encoded_query(table: str, query: str, fields: str = "", limit: int = 20) -> str:
    """Run a ServiceNow encoded query and return results. Useful for complex filters.

    Args:
        table: Table name
        query: ServiceNow encoded query (e.g., 'active=true^stateIN1,2^ORDERBYDESCsys_created_on')
        fields: Comma-separated fields to return
        limit: Max records
    """
    params = {"sysparm_query": query, "sysparm_limit": limit}
    if fields:
        params["sysparm_fields"] = fields

    async with httpx.AsyncClient(verify=False, timeout=30) as client:
        r = await client.get(_table_url(table), headers=_auth_headers(), params=params)
        return r.text


# --- Entry Point ---

if __name__ == "__main__":
    mcp.run(transport="stdio")
