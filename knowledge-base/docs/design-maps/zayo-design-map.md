# Zayo Bridge Portal — Figma Design Map

## Figma File
- **File**: Zayo Design File
- **fileKey**: `IswYFHKrZNMv5DHdylqxcP`
- **Page**: Mockups R1 (nodeId: `0:1`)
- **Prototype start**: Homepage (nodeId: `1:327`)

## Pages / Screens

### 1. Homepage (Dashboard)
- **nodeId**: `1:327`
- **Description**: Main dashboard with account overview, services, orders, and billing
- **Widgets needed**:

| Widget | Description | SN Tables |
|--------|-------------|-----------|
| `zayo-nav-header` | Top navigation bar with Zayo Bridge logo, tabs (Dashboard, My Cases, My Orders), notifications, profile | sp_header_footer, sys_user |
| `zayo-welcome-banner` | Welcome message + AI Assist search bar | sys_user |
| `zayo-quick-actions` | My Cases and My Orders cards with counts and View All links | sn_customerservice_case, custom order table |
| `zayo-recent-orders` | Order list with ID, category tags, status tags, dates, prices | Custom order table |
| `zayo-account-overview` | Company name, account #, type (Enterprise), status, last login | core_company, sys_user |
| `zayo-active-services` | List of active services with location counts and status | Custom services table |
| `zayo-contract-billing` | Contact info, billing info, service address, quick action links | core_company, sys_user |
| `zayo-action-buttons` | "Submit an Order" and "Create a Case" buttons | Navigation actions |

### 2. My Orders
- **nodeId**: `16:380`
- **Description**: Full order management page with summary stats and order table
- **Widgets needed**:

| Widget | Description | SN Tables |
|--------|-------------|-----------|
| `zayo-orders-stats` | 3 stat cards — Total Orders (18), Actual Services (3), Monthly Recurring ($26K) | Custom order/service tables |
| `zayo-orders-table` | Full data table with Order ID, Item, Category, Status, Milestone Stage, Quantity, Order Date, Expected Delivery, Total | Custom order table |

### 3. My Cases
- **nodeId**: `23:441`
- **Description**: Case management page with case list
- **Widgets needed**:

| Widget | Description | SN Tables |
|--------|-------------|-----------|
| `zayo-cases-header` | Title, description, "Create New Case" button | sn_customerservice_case |
| `zayo-cases-table` | Case table with Case ID, Title, State, Priority, Created, Last Updated, Assignee | sn_customerservice_case |

### 4. My Profile (Account Settings)
- **nodeId**: `33:1791`
- **Description**: Profile management with tabs for Profile, Contacts & Billing, Notifications, Security
- **Widgets needed**:

| Widget | Description | SN Tables |
|--------|-------------|-----------|
| `zayo-profile-tabs` | Tab navigation — Profile, Contacts & Billing, Notifications, Security | sys_user |
| `zayo-profile-form` | Personal info form (name, email, phone, job title) + Company info (company name, address) + Save button | sys_user, core_company |

## Design Tokens (Extracted from Screenshots)

### Colors
```
Primary (dark blue):    #0B2A3C (nav header, section headers)
Accent (orange):        #E87722 (buttons, active states, "Submit" actions)
Success (green):        #28A745 (Active status tags)
Warning (yellow/orange): #E87722 (In Process, Provisioning tags)
Info (teal):            #17A2B8 (category tags like "Waves")
Dark tag:               #343A40 (Dark Fiber, Colocation tags)
Background:             #F5F7FA (page background)
Card background:        #FFFFFF
Text primary:           #212529
Text secondary:         #6C757D
```

### Typography
```
Headings:       600 weight, dark blue (#0B2A3C)
Body text:      400 weight, #212529
Secondary text: 400 weight, #6C757D
Button text:    600 weight, white on primary/accent
```

### Spacing
```
Card padding:    24px
Section gap:     16-24px
Table row height: ~60px
Border radius:   8-12px (cards), 16px (tags)
```

## Widget-to-Page Mapping

### Portal: `zayo-bridge`
### Theme: `zayo-bridge-theme`

| Page ID | Page Title | Widgets |
|---------|-----------|---------|
| `zayo-home` | Dashboard | zayo-nav-header, zayo-welcome-banner, zayo-quick-actions, zayo-recent-orders, zayo-account-overview, zayo-active-services, zayo-contract-billing, zayo-action-buttons |
| `zayo-orders` | My Orders | zayo-nav-header, zayo-orders-stats, zayo-orders-table |
| `zayo-cases` | My Cases | zayo-nav-header, zayo-cases-header, zayo-cases-table |
| `zayo-profile` | My Profile | zayo-nav-header, zayo-profile-tabs, zayo-profile-form |

## Implementation Priority
1. Portal + Theme + CSS (foundation)
2. Nav header (shared across all pages)
3. Homepage widgets (highest visibility)
4. Orders page
5. Cases page
6. Profile page
