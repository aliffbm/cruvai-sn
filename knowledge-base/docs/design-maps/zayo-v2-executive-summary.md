# Zayo Bridge Portal V2 — Executive Summary

## Overview

A fully functional B2B customer portal has been built on ServiceNow, designed from the Zayo Bridge Figma mockups. The portal gives external business customers a single pane of glass to manage their account, cases, orders, services, and knowledge — all branded to the Zayo design system.

**Portal URL:** https://fishbonedemo10.service-now.com/zayo_v2

A dedicated demo user with the appropriate customer-facing permissions (no admin access) will be provided shortly for walkthrough and testing.

## What Was Built

### 12 Fully Functional Pages

| Page | Description |
|------|-------------|
| **Dashboard** | Personalized homepage with time-of-day greeting, AI Assist search bar, quick action cards (Cases, Orders, KB), recent orders, account overview, and active services |
| **My Cases** | Summary statistics and a full case list with state and priority indicators, plus a "Create New Case" action |
| **Case Detail** | Individual case view with full case information, comment history, and assigned personnel |
| **Create Case** | Case creation using ServiceNow's native Record Producer framework — ensures all business rules, validations, and workflows fire correctly |
| **My Orders** | Order statistics (in-flight, active services, active orders) and a detailed order table with status tracking |
| **Order Detail** | Individual order view with order information, activity timeline, and account context |
| **Active Services** | Service inventory table showing health, environment, ownership, and criticality for all services tied to the customer's account |
| **Knowledge Base** | Two-column layout with popular articles, recently added content, category browsing, quick help links, and a feedback section |
| **KB Article** | Individual article view with related articles, helpfulness rating, and a path to create a support case |
| **Search** | Global search across cases and knowledge articles |
| **Account / Profile** | Account information, user profile, contact management, and security settings |
| **Portal Documentation** | Live technical reference page with architecture details, widget inventory, data sources, and design patterns used |

### Key Capabilities

- **Account-scoped data** — All data is automatically filtered to the logged-in customer's account. Customers only see their own cases, orders, and services.
- **Real ServiceNow data** — The portal queries live ServiceNow tables (CSM Cases, Orders, Install Base, Knowledge Base) — not mock data.
- **Native case creation** — Uses ServiceNow's Record Producer framework so all business rules, approvals, and workflows function as expected.
- **Consistent design system** — Exo 2 typography, Zayo color palette (teal primary, navy headers), and responsive card-based layouts matching the Figma designs.

### ServiceNow Platform Integration

The portal leverages standard CSM platform capabilities:

- **CSM Cases** for support case management
- **Order Management** for order tracking
- **Install Base** linked to **CMDB Services** for the active services inventory
- **Knowledge Management** for self-service content
- **Record Producers** for guided case creation
- **Customer Account model** for B2B data isolation

### Rapid Development Process

A reusable development toolkit and process was established alongside this build. Future portals can be created from a Figma design in a fraction of the traditional development time using the same approach — including automated design analysis, OOB component reuse evaluation, and scripted deployment.

---

*Built on ServiceNow Zurich (Patch 7) — fishbonedemo10.service-now.com*
