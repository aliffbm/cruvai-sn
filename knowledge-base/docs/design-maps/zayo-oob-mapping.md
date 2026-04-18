# Zayo Bridge Portal — OOB CSM Mapping

## OOB CSM Portal
- **Portal**: Customer Support (`csm`, sys_id: `89275a53cb13020000f8d856634c9c51`)
- **URL**: `https://dev219386.service-now.com/csm`

## OOB Pages Available

| OOB Page | Page ID | Zayo Equivalent |
|----------|---------|-----------------|
| Customer Service Portal (Index) | `csm_index` | Homepage / Dashboard |
| Cases | `csm_cases` | My Cases |
| Cases And Tasks | `portal_cases_and_tasks` | My Cases (alternative) |
| Portal Cases | `portal_cases` | My Cases (newer) |
| Orders | `customer_orders` | My Orders |
| Orders (Portal) | `portal_customer_orders` | My Orders (newer) |
| Order Details | `customer_order_details` | Order detail view |
| Create an Order | `create_order_catalog_item_rp` | Submit an Order button target |
| Create Case | `contributor_user_create_case` | Create a Case button target |
| Ticket Form for Case | `csm_ticket` | Case detail view |
| User Profile | `csm_profile` | My Profile |
| Products | `csm_sold_products` | Active Services section |
| Product Details | `csm_sold_product_details` | Service detail view |
| Contacts | `csm_contacts` | Contact info section |
| Get Help | `csm_get_help` | AI Assist feature |
| Registration | `csm_registration` | New user registration |
| Login | `csm_login` | Login page |

## OOB Widgets -> Zayo Widget Mapping

### Navigation / Layout
| OOB Widget | Widget ID | Zayo Section | Action |
|------------|-----------|--------------|--------|
| CSM Unified Portal Header | `csm-unified-portal-header` | Top nav bar | **CLONE & CUSTOMIZE** — rebrand with Zayo logo, add Dashboard/My Cases/My Orders tabs |
| CSM Unified Portal Header Menu Widget | `csm-unified-portal-header-menu-widget` | Nav menu items | **REUSE** with config changes |
| CSM Unified Portal Footer | `csm-unified-portal-footer` | Footer | **CLONE & CUSTOMIZE** |
| CSM Unified Portal Footer Menu Widget | `csm-unified-portal-footer-menu-widget` | Footer menu | **REUSE** |
| My Profile Breadcrumb | `my-profile-breadcrumb` | Back to Dashboard link | **REUSE** |

### Cases
| OOB Widget | Widget ID | Zayo Section | Action |
|------------|-----------|--------------|--------|
| Cases Simple List | `cases-simple-list` | My Cases table | **CLONE & CUSTOMIZE** — add State/Priority tags styling |
| Portal Case Cards | `portal_case_cards` | My Cases quick action card | **CLONE & CUSTOMIZE** — match Zayo card design |
| Case View Widget | `case-view` | Case detail view | **REUSE** |
| Case Ticket Fields | `case-ticket-fields` | Case form fields | **REUSE** |
| Case Ticket Action | `case-ticket-action` | Case actions | **REUSE** |
| CSM Standard Ticket Conversation | `csm-std-ticket-conversation` | Case conversation | **REUSE** |
| Case Related Records | `case-related-records` | Case related items | **REUSE** |

### Orders
| OOB Widget | Widget ID | Zayo Section | Action |
|------------|-----------|--------------|--------|
| Order Information | `order_information_telco` | Recent Orders / Order detail | **CLONE & CUSTOMIZE** — match Zayo table design |
| Order Details Tabs | `order_details_tabs_telco` | Order detail tabs | **REUSE** |
| Order details header | `order_details_header_telco` | Order detail header | **CLONE & CUSTOMIZE** |
| Order Activity with Mail | `copy_csm_convo_telco` | Order activity feed | **REUSE** |
| Order Line Embed | `order_line_embed_telco` | Order line items | **REUSE** |
| SC Order Status | `sc_order_status` | Order status tracking | **REUSE** |

### Account / Profile
| OOB Widget | Widget ID | Zayo Section | Action |
|------------|-----------|--------------|--------|
| User Profile | `user-profile` | My Profile form | **CLONE & CUSTOMIZE** — match Zayo tabs (Profile, Contacts & Billing, Notifications, Security) |
| User Profile Actions | `user-profile-actions` | Profile actions | **REUSE** |
| Profile Security | `csm_profile_security` | Security tab | **REUSE** |
| RocketFuel My Account | `nr-my-account` | Account Overview | **EVALUATE** — may already have account display logic |
| Customer Registration | `customer-registration` | New user registration | **REUSE** |

### Custom Widgets Needed (No OOB Equivalent)
| Zayo Widget | Description | Why Custom |
|-------------|-------------|------------|
| `zayo-welcome-banner` | Welcome back + AI Assist search bar | No OOB equivalent for AI Assist integration |
| `zayo-account-overview` | Company, Account #, Type, Status, Last Login | OOB CSM doesn't have a dashboard account card |
| `zayo-active-services` | Service list with locations and status | Could extend `csm_sold_products` but Zayo design is different |
| `zayo-contract-billing` | Contact, billing, address, quick actions | No direct OOB equivalent |
| `zayo-orders-stats` | Total Orders, Actual Services, Monthly Recurring stats | No OOB stats cards |
| `zayo-quick-actions` | My Cases / My Orders cards with counts | Could be built from `portal_case_cards` pattern |
| `zayo-action-buttons` | Submit Order / Create Case buttons | Simple custom widget |

## OOB Script Includes to Leverage

### Case Management
| Script Include | API Name | Purpose |
|----------------|----------|---------|
| CSMRelationshipServiceSNC | `global.CSMRelationshipServiceSNC` | Case relationships |
| CSMContentAccessCase | `sn_customerservice.CSMContentAccessCase` | Case content access control |
| CaseTypeHelper | `sn_csm_case_types.CaseTypeHelper` | Case type management |
| CSMRelationshipService_CaseRelatedParty | `sn_customerservice.CSMRelationshipService_CaseRelatedParty` | Case related parties |

### Order Management
| Script Include | API Name | Purpose |
|----------------|----------|---------|
| OrderManagementClientUtil | `sn_csm_om.OrderManagementClientUtil` | Order client utilities |
| OrderLineUtilImpl | `sn_csm_om.OrderLineUtilImpl` | Order line operations |
| OrderLineDAO | `sn_csm_om.OrderLineDAO` | Order line data access |

### Pricing / Billing
| Script Include | API Name | Purpose |
|----------------|----------|---------|
| PricingConstants | `sn_csm_pricing.PricingConstants` | Pricing constants |
| PricingContextBuilderUtils | `sn_csm_pricing.PricingContextBuilderUtils` | Pricing context |
| ListPriceImplementationOOB | `sn_csm_pricing.ListPriceImplementationOOB` | List price logic |
| CostImplementationOOB | `sn_csm_pricing.CostImplementationOOB` | Cost calculation |

### Lookup / Verification
| Script Include | API Name | Purpose |
|----------------|----------|---------|
| CSMLookupVerifyUtil | `sn_csm_lv.CSMLookupVerifyUtil` | Customer lookup/verify |
| CSMLookupVerifyAjaxUtil | `sn_csm_lv.CSMLookupVerifyAjaxUtil` | Client-side lookup |

## Implementation Strategy: OOB-First Approach

### Phase 1: Foundation (OOB)
1. Clone CSM portal → create `zayo-bridge` portal
2. Clone CSM theme → create `zayo-bridge-theme` with Zayo colors
3. Clone CSM header → rebrand with Zayo logo and navigation
4. Set up pages: `zayo-home`, `zayo-orders`, `zayo-cases`, `zayo-profile`

### Phase 2: Reuse OOB Widgets (Configure, Don't Rebuild)
1. Use `cases-simple-list` for My Cases table (customize CSS only)
2. Use `order_information_telco` for Orders table (customize CSS)
3. Use `user-profile` for Profile page (add tabs via CSS/config)
4. Use `csm_profile_security` for Security tab
5. Use `case-view`, `case-ticket-fields`, `case-ticket-action` as-is

### Phase 3: Clone & Customize (Extend OOB)
1. Clone `csm-unified-portal-header` → `zayo-nav-header`
2. Clone `portal_case_cards` → `zayo-quick-actions`
3. Clone `order_details_header_telco` → `zayo-order-header`

### Phase 4: Build Custom (Only What's Missing)
1. `zayo-welcome-banner` — AI Assist integration
2. `zayo-account-overview` — Dashboard account card
3. `zayo-active-services` — Services list
4. `zayo-contract-billing` — Billing info card
5. `zayo-orders-stats` — Stats summary cards
6. `zayo-action-buttons` — CTA buttons
