# CSM B2B Portal Agent Profile

## Domain
Customer Service Management (CSM) portals for B2B/enterprise customers. These portals serve external business customers who need to manage cases, orders, services, and account information.

## OOB Portal Reference
- **Business Portal** (`/business_portal`) — The newer B2B architecture using `sn_ciwf_ui_cmpnt` widget library
- **CSM Portal** (`/csm`) — Older architecture, global-scope widgets

**Follow the Business Portal pattern** — it's newer, cleaner, and more configurable.

## Key Application Scopes
| Scope | API Name | Purpose |
|-------|----------|---------|
| Customer Service | `sn_customerservice` | Core CSM data model |
| Order Management | `sn_csm_om` | Order lifecycle |
| Price Management | `sn_csm_pricing` | Pricing engine |
| Case Types | `sn_csm_case_types` | Extensible case framework |
| Lookup Verify | `sn_csm_lv` | Customer lookup (client-callable) |
| Install Base | `sn_install_base` | Products/services |
| UI Components | `sn_ciwf_ui_cmpnt` | Business Portal widgets |
| Knowledge Mgmt SP | `sn_km_portal` | KB widgets |

## Primary Tables
| Table | Purpose | Typical Queries |
|-------|---------|-----------------|
| `sn_customerservice_case` | Cases | `state IN 18,1,10` (New/Open/Awaiting) |
| `sn_ind_tmt_orm_order` | Telecom orders | `orderByDesc sys_created_on` |
| `sc_order` / `sc_req_item` | Service catalog orders | Fallback for orders |
| `sn_csm_sold_product` | Installed products/services | `install_status=1` |
| `customer_account` | CSM accounts | Link via `company` field |
| `core_company` | Company records | `sys_user.company` |
| `kb_knowledge` | Knowledge articles | `workflow_state=published` |
| `sys_choice` | Choice lists | For dropdowns (category, priority) |
| `sc_cat_item_producer` | Record producers | `table_name=sn_customerservice_case` |

## Key Script Includes
| Script Include | Scope | Client-Callable | Use For |
|----------------|-------|-----------------|---------|
| `CSMLookupVerifyUtil` | `sn_csm_lv` | Yes | Customer lookup/verification |
| `CSMLookupVerifyAjaxUtil` | `sn_csm_lv` | Yes | Client-side lookup |
| `OrderManagementClientUtil` | `sn_csm_om` | Yes | Order utilities |
| `CustomerAccountAPI` | `sn_csm_om` | No | Account API |
| `CSMRelationshipServiceSNC` | global | No | Case relationships |
| `CaseTypeHelper` | `sn_csm_case_types` | No | Case type management |

## OOB Widgets to Evaluate for Reuse
| Widget | ID | Scope | Best For |
|--------|----|-------|----------|
| Portal Banner | `portal-banner` | `sn_ciwf_ui_cmpnt` | Hero with personalized greeting |
| Portal Case Cards | `portal_case_cards` | `sn_ciwf_ui_cmpnt` | Active case tracking |
| Portal Quick Links | `portal_quick_links` | `sn_ciwf_ui_cmpnt` | Navigation CTAs |
| Portal Knowledge Quick Links | `portal_knowledge_quick_links` | `sn_ciwf_ui_cmpnt` | KB article carousel |
| Portal Catalog Quick Links | `portal_catalog_quick_links` | `sn_ciwf_ui_cmpnt` | Catalog items |
| SC Catalog Item | `widget-sc-cat-item-v2` | global | Record producer forms |
| Cases Simple List | `cases-simple-list` | global | Case list tables |
| CSM Unified Portal Header | `csm-unified-portal-header` | global | Nav header reference |

## B2B Data Patterns

### Account Scoping
All B2B queries MUST scope by account:
```javascript
var user = gs.getUser();
var userGR = new GlideRecord("sys_user");
userGR.get(user.getID());
var companyId = userGR.getValue("company");

var gr = new GlideAggregate("sn_customerservice_case");
gr.addQuery("account.company", companyId);
```

### Case State Filtering
Business Portal filters cases by actionable states:
- State 18 = New
- State 1 = Open
- State 10 = Awaiting Info
```javascript
caseGR.addQuery("state", "IN", "18,1,10");
```

### Time-of-Day Greeting
```javascript
var now = new GlideDateTime();
var hour = parseInt(now.getLocalTime().toString().substring(0, 2)) || 12;
var greeting = hour < 12 ? "Good morning" : (hour < 17 ? "Good afternoon" : "Good evening");
```

### Record Producer for Case Creation
Never use direct GlideRecord insert. Use OOB Record Producers:
```javascript
var rpGR = new GlideRecord("sc_cat_item_producer");
rpGR.addActiveQuery();
rpGR.addQuery("table_name", "sn_customerservice_case");
rpGR.query();
// Show selection UI, then embed:
data.catItemWidget = $sp.getWidget("widget-sc-cat-item-v2", { sys_id: selectedRP });
```

### Table Fallback Chain
```javascript
// Try industry-specific table first
var gr = new GlideRecord("sn_ind_tmt_orm_order");
if (gr.isValid()) {
  // query it
} else {
  // fallback to sc_order
}
```

## Standard Page Map for CSM B2B
| Page | Widget Sections | Data Sources |
|------|----------------|--------------|
| Dashboard | Welcome banner, Quick actions (3 cards), Recent orders, Account overview, Active services | `sys_user`, `sn_customerservice_case`, `sn_ind_tmt_orm_order`/`sc_order`, `core_company`, `sn_csm_sold_product` |
| My Orders | Stats cards (3), Orders data table | `sn_ind_tmt_orm_order`/`sc_order` |
| Order Detail | Order info grid, Activity timeline, Account sidebar | `sn_ind_tmt_orm_order`/`sc_order`, `sys_audit` |
| My Cases | Stats cards (3) + Create button, Cases data table | `sn_customerservice_case` |
| Case Detail | Case info grid, Comments timeline, People sidebar | `sn_customerservice_case`, `sys_journal_field` |
| Create Case | Record Producer selection, Embedded SC Catalog Item form | `sc_cat_item_producer`, `widget-sc-cat-item-v2` |
| Active Services | Services data table | `sn_csm_sold_product`/`cmdb_ci_service` |
| Knowledge Base | Search, Popular articles, Recently added, Browse by category, Quick help | `kb_knowledge`, `GlideAggregate` by `kb_category` |
| KB Article | Article content, Related articles, Helpful rating | `kb_knowledge`, `sys_journal_field` |

## Design Token Defaults (Zayo Reference)
```css
:root {
  --brand-primary: #0B2A3C;    /* Nav, section headers */
  --brand-accent: #E87722;     /* Buttons, active states */
  --brand-success: #28A745;    /* Active/healthy tags */
  --brand-bg: #F5F7FA;         /* Page background */
  --brand-card-bg: #FFFFFF;    /* Card backgrounds */
  --brand-text: #212529;       /* Primary text */
  --brand-text-muted: #6C757D; /* Secondary text */
}
```
Override these with values extracted from the Figma design.
