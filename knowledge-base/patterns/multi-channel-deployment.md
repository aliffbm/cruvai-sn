# Multi-Channel Deployment Guide

## Available Channels

| Channel | Best For | Limitation |
|---------|----------|------------|
| **SN SDK (Fluent DSL)** | Tables, ACLs, flows, catalog items, business rules, script includes | Requires `now-sdk` CLI setup |
| **REST API** | Portal pages, themes, CSS configs, bulk CRUD on any table | HTML gets sanitized on `sp_widget.template` |
| **sn-scriptsync** | Widget HTML templates, live editing, real-time preview | Requires browser with SN Utils extension |
| **MCP Server** | AI-assisted CRUD, schema discovery, catalog building | Subset of REST API capabilities |

## Channel Selection Decision Tree

```
What are you deploying?
│
├─ Table/ACL/Flow/Catalog Item/Business Rule
│  → SN SDK (Fluent DSL)
│
├─ SP Widget with HTML template
│  → sn-scriptsync Agent API (avoids REST HTML sanitization)
│     Fallback: SN SDK SPWidget()
│
├─ SP Widget (scripts/CSS only, no HTML)
│  → REST API or sn-scriptsync (both work)
│
├─ SP Page/Theme/CSS config
│  → REST API POST to sp_page, sp_theme, sp_css
│
├─ Live editing (any widget field)
│  → sn-scriptsync (real-time WebSocket sync)
│
└─ Bulk data operations
   → REST API (fastest for bulk CRUD)
```

## Critical: REST API HTML Sanitization

The REST API sanitizes HTML content in `sp_widget.template` even when `glide.rest.sanitize_request_input` is set to `false`. This means:

- **DO NOT** use REST API to set widget HTML templates
- **DO** use sn-scriptsync Agent API `create_artifact` command for HTML content
- Scripts (client_script, server_script) and CSS work fine via REST API

## REST API Notes

- Use PUT (not PATCH) for `sp_widget` updates — PATCH fails on this table
- Requires `admin` or `sp_admin` role for portal tables
- Endpoint pattern: `GET/POST/PUT/DELETE /api/now/table/{table_name}`

## sn-scriptsync Notes

- Requires SN Utils browser extension + active browser session
- Agent API: write JSON to `_requests.json`, read from `_responses.json`
- Not suitable for CI/CD (requires interactive browser)
- Best for development and iterative editing
