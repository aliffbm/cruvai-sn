# Employee Center Portal Agent Profile

## Domain
Employee-facing portals for internal service delivery (IT, HR, Facilities). Employees submit requests, track cases, browse the service catalog, and access knowledge articles.

## OOB Portal Reference
- **Employee Center** (`/esc`) — Modern employee experience, topic-based navigation
- **Employee Center Pro** (`/esc`) — Enhanced version with configurable layouts
- **Service Portal** (`/sp`) — Classic IT self-service portal

**Follow the Employee Center pattern** — it's the modern standard for internal portals.

## Key Application Scopes
| Scope | API Name | Purpose |
|-------|----------|---------|
| Employee Center | `sn_employee_center` | Core EC framework |
| Employee Center Core | `sn_hr_sp` | HR case integration |
| HR Service Delivery | `sn_hr_core` | HR cases and lifecycle events |
| Service Catalog | `sn_sc` | Request management |
| Knowledge Management SP | `sn_km_portal` | KB widgets |
| Workplace Service Delivery | `com.sn_wsd` | Facilities/workplace |

## Primary Tables
| Table | Purpose | Typical Queries |
|-------|---------|-----------------|
| `sc_request` | Service requests | `requested_for=current_user` |
| `sc_req_item` | Request items | `request.requested_for=current_user` |
| `sc_task` | Catalog tasks | `request_item.request.requested_for=current_user` |
| `incident` | Incidents | `caller_id=current_user` |
| `sn_hr_core_case` | HR cases | `opened_for=current_user` |
| `kb_knowledge` | Knowledge articles | `workflow_state=published` |
| `sc_cat_item` | Catalog items | `active=true` |
| `sc_category` | Catalog categories | `active=true` |
| `topic` | EC Topics | For topic-based navigation |
| `sys_user` | User profile | Current user info |

## Key OOB Widgets
| Widget | ID | Use For |
|--------|----|---------|
| EC Unified Header | (EC-specific) | Navigation |
| SC Category Page | `sc-category-page` | Catalog browsing |
| SC Catalog Item | `widget-sc-cat-item-v2` | Request forms |
| My Requests | (various) | Request tracking |
| KB Article | `kb-article-page` | Article display |
| Approval Record | `approval-record` | Approvals |
| Typeahead Search | `typeahead-search` | Search |

## Standard Page Map for Employee Center
| Page | Widget Sections | Data Sources |
|------|----------------|--------------|
| Home | Welcome banner, Featured topics, Quick links, My requests summary, Announcements | `sys_user`, `sc_request`, `topic`, `kb_knowledge` |
| Browse Services | Category grid, Service catalog items | `sc_category`, `sc_cat_item` |
| My Requests | Request list with status tracking | `sc_request`, `sc_req_item`, `sc_task` |
| Request Detail | Request info, Approval status, Activity | `sc_req_item`, `sysapproval_approver` |
| Knowledge Base | Search, Categories, Articles | `kb_knowledge`, `kb_category` |
| My Profile | User info, Preferences | `sys_user` |
| HR Hub | HR services, Life events, HR cases | `sn_hr_core_case`, `sn_hr_le_case` |

## Data Patterns

### User-Scoped (not account-scoped like B2B)
```javascript
var userId = gs.getUserID();
var gr = new GlideRecord("sc_request");
gr.addQuery("requested_for", userId);
```

### Catalog Category Browsing
```javascript
var catGR = new GlideRecord("sc_category");
catGR.addActiveQuery();
catGR.addQuery("parent", ""); // top-level categories
catGR.orderBy("order");
```

### Request Status Tracking
```javascript
var reqGR = new GlideRecord("sc_req_item");
reqGR.addQuery("request.requested_for", gs.getUserID());
reqGR.orderByDesc("sys_created_on");
```

## Notes
- Employee Center uses **topic-based navigation** rather than traditional menu tabs
- Service Catalog is central — most actions go through `sc_cat_item` forms
- HR integration may or may not be present depending on instance plugins
- Announcements/news use `kb_knowledge` with specific knowledge bases
- The visual style tends to be lighter/more colorful than B2B portals
