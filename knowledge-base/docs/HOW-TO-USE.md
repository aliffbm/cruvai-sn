# SNBAWS — How to Build a ServiceNow Portal from Figma

## Quick Start (One-Prompt Portal Build)

### Step 1: Set Up Your Environment
```bash
# Clone the repo
git clone <repo-url> && cd SNBAWS

# Copy and configure .env
cp .env.template .env
# Edit .env with your instance URL, username, password, and app scope
```

### Step 2: Start a Claude Code Session
Open the project in Claude Code (CLI, Desktop, or VS Code extension).

The session startup will automatically:
- Verify `.env` exists
- Test REST API connectivity
- Check user roles
- Report connection status

### Step 3: Build a Portal with One Prompt

**CSM B2B Portal (Customer-facing):**
```
Build a CSM B2B portal from this Figma design:
https://www.figma.com/proto/<your-figma-file-url>

Portal name: [Your Portal Name]
Portal path: /[url-suffix]
App scope: [x_company_portal]
```

**Employee Center Portal (Employee-facing):**
```
Build an Employee Center portal from this Figma design:
https://www.figma.com/proto/<your-figma-file-url>

Portal name: [Your Portal Name]
Portal path: /[url-suffix]
App scope: [x_company_esc]
```

**Custom Portal:**
```
Build a custom portal from this Figma design:
https://www.figma.com/proto/<your-figma-file-url>

Portal name: [Your Portal Name]
Portal path: /[url-suffix]
Portal type: custom
Tables: [list any custom tables this portal will use]
```

---

## What Happens When You Run the Prompt

Claude Code follows the `build-portal` skill (`.claude/skills/build-portal.md`) through 8 phases:

### Phase 1: Figma Capture
- Opens the Figma prototype in Chrome (via Claude in Chrome extension)
- Screenshots every page in the Flows sidebar
- Documents all sections, widgets, and design tokens

### Phase 2: OOB Discovery
- Queries your SN instance for existing portals, themes, widgets
- Loads the appropriate **agent profile** (CSM B2B, Employee Center, etc.)
- Identifies OOB widgets that can be reused vs. custom-built
- **Presents findings for your review** before proceeding

### Phase 3: Design Intent Analysis
- Maps each Figma section to SN tables and query patterns
- Identifies ACLs, script includes, and data scoping needed
- Determines which Record Producers to use for create forms
- **Presents the analysis for your approval**

### Phase 4-6: Build & Deploy
- Creates portal foundation (CSS, Theme, Pages, Portal record)
- Builds all widgets with proper server/client scripts
- Places widgets on pages using the Container/Row/Column/Instance hierarchy
- All records created in your specified app scope

### Phase 7-8: Navigation & Verify
- Wires up nav header across all pages
- Opens the portal in the browser for verification
- Iterates on differences vs. Figma

---

## Portal Types & Agent Profiles

### CSM B2B Portal
**Best for:** External customer portals (case management, orders, services)

**Key features:**
- Account-scoped data (B2B multi-tenancy)
- Case state filtering (New/Open/Awaiting)
- Record Producer-based case creation
- Install Base / Sold Products for services
- Order management (telecom or service catalog)

**OOB reference:** Business Portal (`/business_portal`)
**Agent profile:** `.claude/skills/agents/csm-b2b-portal.md`

### Employee Center Portal
**Best for:** Internal employee self-service (IT, HR, Facilities)

**Key features:**
- User-scoped data (not account-scoped)
- Service catalog browsing and requests
- HR case integration
- Topic-based navigation
- Knowledge Base and announcements

**OOB reference:** Employee Center (`/esc`)
**Agent profile:** `.claude/skills/agents/employee-center-portal.md`

### Custom Portal
**Best for:** Anything that doesn't fit the above patterns

**Key features:**
- No OOB assumptions
- You specify the tables and data model
- Full flexibility on layout and widgets

**Agent profile:** `.claude/skills/agents/custom-portal.md` (create as needed)

---

## Environment Configuration

### Required `.env` Variables
```
SN_INSTANCE_URL=https://your-instance.service-now.com
SN_USERNAME=your-username
SN_PASSWORD=your-password
SN_APP_SCOPE=x_company_portal    # Application scope for scoped development
SN_PORTAL_NAME=My Portal         # Portal display name
SN_PORTAL_PATH=my-portal         # URL suffix
```

### Prerequisites on the Instance
1. **Admin role** for the user (required for REST API writes)
2. **HTML sanitization disabled**: `glide.rest.sanitize_request_input = false`
3. **Application scope created** (if using scoped development)
4. **Chrome browser** with Claude in Chrome extension (for Figma capture)

### Optional
- **Figma MCP** connected (for programmatic design extraction)
- **sn-scriptsync** connected (for live editing after deployment)
- **Node.js 20+** installed (for SN SDK / Fluent DSL)

---

## Key Architectural Rules

### 1. No Hardcoded sys_ids
All scripts discover sys_ids dynamically by querying records by `id` or `name`. This ensures portability across instances.

### 2. Application Scope
All portal records (widgets, pages, themes, CSS) are created in the configured app scope. This enables:
- Clean update set exports
- Deployment to client instances
- Proper access control

### 3. SP Layout Hierarchy
```
sp_page
  -> sp_container (order, width: container/container-fluid)
       -> sp_row (order)
            -> sp_column (size 1-12)
                 -> sp_instance (widget + order)
```
**Skipping any layer causes widgets not to render.**

### 4. Record Producers for Create Forms
Never create records via direct GlideRecord insert in portal widgets. Use OOB Record Producers rendered through the `widget-sc-cat-item-v2` widget.

### 5. Account Scoping (B2B only)
All B2B data queries scope by `sys_user.company` -> `account.company`.

### 6. Graceful Table Fallbacks
Always check `gr.isValid()` before querying industry-specific tables. Provide fallbacks to standard tables.

---

## Project Structure
```
SNBAWS/
  .claude/
    skills/
      build-portal.md          # Master portal builder skill
      figma-to-sn.md           # Figma conversion reference
      sn-create-widget.md      # Widget code patterns
      sn-crud-operations.md    # REST API patterns
      sn-connect.md            # Instance connection skill
      agents/
        csm-b2b-portal.md      # CSM B2B agent profile
        employee-center-portal.md  # Employee Center agent profile
    STATUS.md                  # Current project status
  docs/
    csm-portal-architecture.md # OOB CSM/Business Portal reference
    channel-routing.md         # REST vs sn-scriptsync routing
  scripts/
    sn-api.sh                  # REST API shell helpers
    deploy-*.py                # Python deployment scripts
  .env                         # Instance credentials (gitignored)
  .env.template                # Template for new engineers
  HOW-TO-USE.md                # This file
  CLAUDE.md                    # Claude Code project instructions
```

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| Widgets not rendering | Check SP layout hierarchy — did you create all layers (Container/Row/Column/Instance)? |
| HTML stripped from widgets | Ensure `glide.rest.sanitize_request_input = false` |
| 403 on REST API PATCH | User needs admin role |
| Figma screenshots not loading | Wait longer, or use Figma MCP instead of browser |
| Record Producer form not loading | Check that the RP `sys_id` is correct and the RP is active |
| Data not showing | Check account scoping — is the user's company linked to the right account? |
| Python `UnicodeEncodeError` | Use Anaconda Python, not Windows Store Python |

---

## Adding a New Portal Type

1. Create a new agent profile: `.claude/skills/agents/[type]-portal.md`
2. Document:
   - Key application scopes and tables
   - OOB widgets to evaluate
   - Data patterns (user-scoped vs. account-scoped)
   - Standard page map
   - Design token defaults
3. Add the type to the agent profile table in `build-portal.md`
4. Test by building a portal with the new profile
