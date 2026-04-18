# sn-scriptsync Agent API Reference

## Prerequisites
1. **SN Utils browser extension** installed (Chrome/Firefox/Edge)
2. **sn-scriptsync VS Code extension** installed (already done)
3. Browser logged into `https://dev219386.service-now.com`
4. SN Utils helper tab open in browser

## How It Works
The Agent API uses a **file-based queue**:
- Write JSON requests to `_requests.json` in the workspace root
- Read JSON responses from `_responses.json`
- No HTTP server needed — just file I/O

## Available Commands

### check_connection
Verify the WebSocket connection is active.
```json
{"id": "1", "command": "check_connection"}
```

### query_records
Query any ServiceNow table.
```json
{
  "id": "2",
  "command": "query_records",
  "table": "sys_script_include",
  "query": "name=MyScriptInclude",
  "fields": "sys_id,name,script",
  "limit": 10
}
```

### create_artifact
Create a new record (script, widget, etc.).
```json
{
  "id": "3",
  "command": "create_artifact",
  "table": "sys_script_include",
  "name": "MyNewScriptInclude",
  "fields": {
    "script": "var MyNewScriptInclude = Class.create();\nMyNewScriptInclude.prototype = {\n    initialize: function() {},\n    type: 'MyNewScriptInclude'\n};",
    "active": true
  }
}
```

### update_record
Update an existing record by sys_id.
```json
{
  "id": "4",
  "command": "update_record",
  "table": "sys_script_include",
  "sys_id": "abc123...",
  "fields": {
    "script": "// updated script content"
  }
}
```

### update_record_batch
Update multiple records at once.
```json
{
  "id": "5",
  "command": "update_record_batch",
  "updates": [
    {"table": "sys_script_include", "sys_id": "abc123", "fields": {"active": false}},
    {"table": "sys_script_include", "sys_id": "def456", "fields": {"active": false}}
  ]
}
```

### sync_now
Force immediate sync of all pending changes.
```json
{"id": "6", "command": "sync_now"}
```

### get_sync_status
Check the current sync queue status.
```json
{"id": "7", "command": "get_sync_status"}
```

### switch_context
Switch update set, application scope, or domain.
```json
{
  "id": "8",
  "command": "switch_context",
  "update_set": "My Update Set",
  "scope": "x_myapp"
}
```

### take_screenshot
Capture a screenshot of a ServiceNow page.
```json
{
  "id": "9",
  "command": "take_screenshot",
  "url": "/sp?id=my_page"
}
```

### upload_attachment
Attach a file to a record.
```json
{
  "id": "10",
  "command": "upload_attachment",
  "table": "sp_widget",
  "sys_id": "abc123",
  "file_path": "./assets/logo.png"
}
```

## File Structure for Auto-Sync
When you create files matching this pattern, sn-scriptsync auto-detects and syncs them:
```
{instance}/{scope}/{table}/{name}.{field}.{extension}
```
Example:
```
dev219386/global/sys_script_include/MyUtils.script.js
dev219386/global/sp_widget/my-widget.template.html
dev219386/global/sp_widget/my-widget.css.scss
dev219386/global/sp_widget/my-widget.client_script.js
dev219386/global/sp_widget/my-widget.script.js
```

## Integration with Claude Code
Claude Code can interact with the Agent API by writing to `_requests.json`:
```bash
echo '{"id": "1", "command": "check_connection"}' > _requests.json
# Response appears in _responses.json
cat _responses.json
```
