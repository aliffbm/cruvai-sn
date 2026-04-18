# CSM & Business Portal Architecture Reference

## Overview

ServiceNow provides two main customer-facing portal architectures:
1. **CSM Portal** (`/csm`) — Older, global-scope widgets, search-centric homepage
2. **Business Portal** (`/business_portal`) — Newer B2B architecture, `sn_ciwf_ui_cmpnt` widget library, richer homepage

**For new portal builds, follow the Business Portal pattern** — it's the newer architecture with better widget configurability and B2B-specific features.

## Portal Records

| Portal | sys_id | URL | Theme | Homepage |
|--------|--------|-----|-------|----------|
| Customer Support (CSM) | `89275a53cb13020000f8d856634c9c51` | `/csm` | Portal Next Experience Theme | `csm_index` |
| Business Portal | `f264dbaccbfd52108d3f6a6fc041e4b5` | `/business_portal` | Customer Experience Coral Theme | (custom) |

Both share login page: `csm_login` (`a0e3b3acc3521200b0449f2974d3ae14`)

## CSM Portal Homepage Layout

4 containers, search-focused:

| # | Container | Widget | Widget ID | Scope |
|---|-----------|--------|-----------|-------|
| 1 | Hero Search | Homepage Search | *(global)* | global |
| 2 | Search Alt | Typeahead Search | `typeahead-search` | global |
| 3 | Quick Links | Icon Link (x3) | *(global)* | global |
| 4 | KB Triptych | KB MostViewed / Featured / MostUseful | `kb-mostviewed-articles` etc. | `sn_km_portal` |

## Business Portal Homepage Layout

6 containers, feature-rich:

| # | Container | Widget | Widget ID | Scope | Key Config |
|---|-----------|--------|-----------|-------|------------|
| 1 | Hero Banner (fluid) | Portal Banner | `portal-banner` | `sn_ciwf_ui_cmpnt` | Personalized greeting, search, 2 CTAs |
| 2 | Case Tracking | Portal Case Cards | `portal_case_cards` | `sn_ciwf_ui_cmpnt` | Queries `sn_customerservice_case`, states 18/1/10 |
| 3 | Quick Links | Portal Quick Links | `portal_quick_links` | `sn_ciwf_ui_cmpnt` | Carousel, 5 manual links |
| 4 | Topics | Portal Taxonomy Topics | `portal_taxonomy_topics` | `sn_ciwf_ui_cmpnt` | Max 4 topic cards |
| 5 | KB Articles | Portal Knowledge Quick Links | `portal_knowledge_quick_links` | `sn_ciwf_ui_cmpnt` | "Most Viewed" criteria, carousel |
| 6 | Catalog | Portal Catalog Quick Links | `portal_catalog_quick_links` | `sn_ciwf_ui_cmpnt` | Dynamic query, carousel |

## Theme Architecture

### CSM Themes Available
| Theme | sys_id | Used By |
|-------|--------|---------|
| Portal Next Experience Theme | `f548bd34845a1110f87767389929c667` | CSM Portal (current) |
| CSM Default | `517030d1531032007a97e192d5dc34d8` | CSM Portal (alternate) |
| Customer Experience Coral | `60bed96c93131210aa38860754891827` | Business Portal |
| Customer Experience Polaris | `0aa0b7a9bdd73010f8772b09d7aaaf3a` | Gov Service Portal |

### Header/Footer Records
Headers and footers in SP are `sp_header_footer` records containing SCSS/CSS, referenced by themes.
- CSM Unified Portal Header: `451ffe6e3b103200367aee1234efc415` (widget-based, complex nav)
- Portal Polaris Header: `3552f974845a1110f87767389929c604` (CSS-heavy, responsive)
- Portal Next Experience Footer: `5cf9e3234305ce107b228dc226b8f2a2` (masonry links, social icons)

## Key Application Scopes

### Core CSM
| Scope | API Name | Purpose |
|-------|----------|---------|
| Customer Service | `sn_customerservice` | Core CSM data model, cases, contacts, accounts |
| Order Management | `sn_csm_om` | Order lifecycle, order lines |
| Price Management | `sn_csm_pricing` | Pricing engine (15+ script includes) |
| Case Types | `sn_csm_case_types` | Extensible case type framework |
| Lookup Verify | `sn_csm_lv` | Customer lookup/verification (client-callable) |
| Install Base | `sn_install_base` | Products/services installed at customer |

### Portal UI
| Scope | API Name | Purpose |
|-------|----------|---------|
| UI Components for Customer Portals | `sn_ciwf_ui_cmpnt` | All Business Portal widgets |
| CSM Unified Theme | `sn_csm_uni_theme` | CSM theme utilities |
| Knowledge Management SP | `sn_km_portal` | KB widgets for Service Portal |
| Business Portal | `sn_b2b_portal` | B2B-specific UI scripts |

## Key Script Includes

### Case Management
| Script Include | API Name | Client-Callable | Purpose |
|----------------|----------|-----------------|---------|
| CSMRelationshipServiceSNC | `global.CSMRelationshipServiceSNC` | No | Case relationships |
| CSMContentAccessCase | `sn_customerservice.CSMContentAccessCase` | No | Case content access control |
| CaseTypeHelper | `sn_csm_case_types.CaseTypeHelper` | No | Case type management |
| CSMLookupVerifyUtil | `sn_csm_lv.CSMLookupVerifyUtil` | Yes | Customer lookup/verify |
| CSMLookupVerifyAjaxUtil | `sn_csm_lv.CSMLookupVerifyAjaxUtil` | Yes | Client-side lookup |

### Order Management
| Script Include | API Name | Client-Callable | Purpose |
|----------------|----------|-----------------|---------|
| OrderManagementClientUtil | `sn_csm_om.OrderManagementClientUtil` | Yes | Order client utilities |
| OrderLineUtilImpl | `sn_csm_om.OrderLineUtilImpl` | No | Order line operations |
| OrderLineDAO | `sn_csm_om.OrderLineDAO` | No | Order line data access |
| CustomerAccountAPI | `sn_csm_om.CustomerAccountAPI` | No | Customer account API |

### Pricing
| Script Include | API Name | Purpose |
|----------------|----------|---------|
| PricingConstants | `sn_csm_pricing.PricingConstants` | Constants |
| PricingContextBuilderUtils | `sn_csm_pricing.PricingContextBuilderUtils` | Pricing context |
| ListPriceImplementationOOB | `sn_csm_pricing.ListPriceImplementationOOB` | List price logic |

## Angular Providers
| Provider | Type | Scope | Purpose |
|----------|------|-------|---------|
| `csmUnifiedDeviceType` | service | `sn_csm_uni_theme` | Device type detection |
| `caseTypePagination` | directive | `sn_csm_case_types` | Case list pagination |
| `addOrderTabAccessibility` | directive | `sn_csm_om` | Order tab a11y |

## UI Scripts
| Script | Scope | Purpose |
|--------|-------|---------|
| `csm_util` | `sn_csm_uni_theme` | Core client-side CSM utilities |
| `Knowledge Portal Service` | `sn_km_portal` | KB service layer |
| `embedabbles` | `sn_b2b_portal` | B2B embeddable widget support |

## B2B Design Patterns

### 1. Widget Configuration via Instance Options
Business Portal widgets are configured entirely through `widget_parameters` JSON on `sp_instance` records. This means the same widget can serve different purposes without code changes:
```json
{
  "title": "Most trending articles",
  "table": "kb_knowledge",
  "criteria_based": "Most Viewed",
  "max_entries": "9",
  "show_carousel": "true"
}
```

### 2. Account Context
B2B portals automatically scope data to the logged-in user's account/company via CSM's account-contact model:
- `sn_customerservice_case` — filtered by account
- `sn_ind_tmt_orm_order` — filtered by account  
- `sn_csm_sold_product` — filtered by account
Use `gs.getUser()` → `sys_user.company` → `core_company` for account context.

### 3. Case State Filtering
Business Portal Case Cards filter by specific states:
- State 18 = New
- State 1 = Open  
- State 10 = Awaiting Info
This shows only actionable cases, not resolved/closed ones.

### 4. Personalized Greetings
Portal Banner uses time-of-day personalization: `<part_of_day>, <user>!`
- Morning / Afternoon / Evening based on user's timezone

### 5. Carousel Pattern
Multiple widgets use carousel display for lists (Quick Links, KB Articles, Catalog Items).
Implemented via instance options: `"show_carousel": "true"`.

### 6. Taxonomy Navigation
Business Portal uses `portal_taxonomy` page with tab-based browsing (catalog vs. KB).
Topics are configured as taxonomy records, not hardcoded.

## SP Page Layout Hierarchy (Critical!)

```
sp_page
  └── sp_container (linked to page, order + width)
        └── sp_row (linked to container, order)
              └── sp_column (linked to row, size 1-12)
                    └── sp_instance (linked to column + widget, order + widget_parameters)
```

**Every layer is required.** Skipping `sp_container` causes widgets not to render.

Container widths:
- `container` — standard (960-1140px)
- `container-fluid` — full viewport width (for hero banners)
