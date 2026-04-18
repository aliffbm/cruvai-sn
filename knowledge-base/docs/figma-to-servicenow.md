# Figma-to-ServiceNow Architecture

## Overview

This document describes the architecture for converting Figma designs into ServiceNow Service Portal widgets, pages, and applications. It leverages the Figma MCP tools available in Claude Code to read design context and generate SN artifacts.

## Available Figma MCP Tools

Claude Code has access to these Figma tools:

| Tool | Purpose |
|------|---------|
| `get_screenshot` | Capture a visual screenshot of any Figma node |
| `get_design_context` | **Primary tool** — returns reference code, screenshot, and metadata |
| `get_metadata` | Get XML structure overview (node IDs, types, names, positions) |
| `get_variable_defs` | Get design token variables (colors, spacing, fonts) |
| `search_design_system` | Search for components, variables, styles in design libraries |
| `get_code_connect_map` | Map Figma nodes to code components |
| `whoami` | Check authenticated Figma user and org access |

## Workflow: Figma Design to SN Widget

### Step 1: Get Page Structure
Use `get_metadata` with the page node ID to see all frames/components on a page.
```
Input: Figma URL (e.g., https://figma.com/design/ABC123/MyApp?node-id=0-1)
Extract: fileKey = "ABC123", nodeId = "0:1"
Tool: get_metadata(fileKey, nodeId)
Output: XML tree of all nodes with IDs, types, names, positions
```

### Step 2: Get Design Context for Each Component
For each widget/component identified in step 1, use `get_design_context`.
```
Tool: get_design_context(fileKey, nodeId)
Output: Reference code (HTML/CSS), screenshot, metadata
```

### Step 3: Extract Design Tokens
Pull variables for consistent theming.
```
Tool: get_variable_defs(fileKey, nodeId)
Output: Color definitions, spacing tokens, font definitions
```

### Step 4: Generate SN Artifacts
Map Figma output to ServiceNow:

| Figma Concept | SN Artifact | Channel |
|---------------|-------------|---------|
| Page/Frame | sp_page | REST API |
| Component | sp_widget | sn-scriptsync (for HTML) or SDK |
| Color variables | sp_css / sp_theme | REST API |
| Text styles | CSS in widget | sn-scriptsync |
| Icons/Images | sys_attachment on widget | REST API |
| Layout (auto-layout) | Bootstrap grid in template | Generated HTML |
| Interactive states | Client script + Angular | sn-scriptsync |
| Data display | Server script + GlideRecord | sn-scriptsync |

### Step 5: Deploy and Preview
- Deploy via appropriate channel (see channel-routing.md)
- Preview at: `https://{instance}/sp?id={page_id}`

## Figma URL Parsing

Given a Figma URL, extract:
```
https://figma.com/design/{fileKey}/{fileName}?node-id={nodeId}

Example:
URL: https://figma.com/design/pqrs/ExampleFile?node-id=1-2
fileKey: "pqrs"
nodeId: "1:2" (replace - with :)
```

For branch URLs:
```
https://figma.com/design/{fileKey}/branch/{branchKey}/{fileName}
Use branchKey as the fileKey
```

## Design Token Mapping

### Colors
```
Figma Variable              -> SN CSS Variable
--color-primary             -> $sp-primary-color
--color-secondary           -> $sp-secondary-color
--color-background          -> $sp-body-bg
--color-text                -> $sp-text-color
```

### Spacing
```
Figma Auto-layout Gap       -> Bootstrap spacing classes
4px                         -> p-1, m-1
8px                         -> p-2, m-2
16px                        -> p-3, m-3
24px                        -> p-4, m-4
```

### Typography
```
Figma Text Style            -> Bootstrap / SN CSS
Heading 1 (32px bold)       -> h1 / .text-display
Heading 2 (24px bold)       -> h2 / .text-headline
Body (16px regular)         -> p / .text-body
Caption (12px)              -> small / .text-caption
```

## Error Handling

- If `get_design_context` returns too much data, use `get_metadata` first to identify specific nodes
- If a component has no code equivalent, generate from scratch using the screenshot as reference
- If design tokens conflict with SN defaults, prefer the Figma design tokens
