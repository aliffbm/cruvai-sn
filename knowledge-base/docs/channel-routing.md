# SNBAWS Channel Routing Guide

## Why Multiple Channels?

ServiceNow has security features that restrict what each connection method can do. No single channel covers everything. This guide documents which channel to use for each operation.

## Channel Matrix

| Operation | SN SDK (Fluent) | REST API | sn-scriptsync | Notes |
|-----------|:-:|:-:|:-:|-------|
| Create tables | X | | | Best via Fluent Table() |
| Create business rules | X | X | X | All channels work |
| Create script includes | X | X | X | All channels work |
| Create client scripts | X | X | X | All channels work |
| Create UI scripts | X | X | X | All channels work |
| Create SP widgets (scripts) | X | X | X | CSS, client/server script all work via API |
| Create SP widgets (HTML) | X | | X | **REST API sanitizes HTML** - use Fluent or sn-scriptsync |
| Create SP pages | | X | | Config records, no HTML |
| Create SP themes | | X | | Config records |
| Create SP CSS | | X | X | |
| Modify sys_properties | | | X | API requires elevated roles |
| Create flows | X | | | Fluent Flow() only |
| Create catalog items | X | | | Fluent only |
| Create ACLs | X | | | Fluent Acl() only |
| Bulk CRUD on data tables | | X | | Table API is fastest |
| Live editing / hot reload | | | X | Real-time via WebSocket |
| Design-to-code (Figma) | X | | | Via MCP + Build Agent |

## Decision Tree

```
Need to create/modify something on SN?
  |
  +-- Is it a table, ACL, flow, or catalog item?
  |     -> Use SN SDK (Fluent)
  |
  +-- Is it an SP widget with HTML template?
  |     -> Use sn-scriptsync (Agent API create_artifact)
  |     -> Or SN SDK SPWidget()
  |     -> NOT REST API (HTML gets sanitized)
  |
  +-- Is it a script artifact (no HTML)?
  |     -> Any channel works
  |     -> REST API for bulk operations
  |     -> sn-scriptsync for live editing
  |
  +-- Is it a portal config record (page, theme)?
  |     -> REST API (POST to sp_page, sp_theme)
  |
  +-- Is it data/records on existing tables?
  |     -> REST API (fastest for CRUD)
  |
  +-- Need real-time preview while editing?
        -> sn-scriptsync (live reload in browser)
```

## Known Limitations

### REST API HTML Sanitization (sp_widget template field)
- **Property**: `glide.rest.sanitize_request_input` (default: `true`)
- **Effect**: Strips HTML tags from POST/PUT/PATCH body fields
- **Impact**: Widget `template` field is sanitized even with property set to `false`
- **Root cause**: The `sp_widget.template` field has additional server-side sanitization beyond the global property
- **Workaround**: Use sn-scriptsync for ALL widget HTML template content — this is the ONLY reliable code-based path
- **What DOES work via REST API**: CSS, client_script, server_script, link function, name, id — all non-HTML fields

### REST API Method Support
- **PATCH** returns 403 on some tables (including `sp_widget`) — use **PUT** instead
- All sn-api.sh helpers use PUT for updates

### sn-scriptsync Browser Dependency
- Requires SN Utils browser extension + active browser session
- WebSocket connection drops if browser tab closes
- Not suitable for CI/CD pipelines (use SDK for that)
