# Service Portal Layout Hierarchy

## Critical Rule
**Every layer in the hierarchy is required.** Skipping any layer (e.g., placing a widget directly on a page without a container/row/column) causes widgets not to render.

## Hierarchy

```
sp_page
  └── sp_container (fields: sp_page, order, width)
        └── sp_row (fields: sp_container, order)
              └── sp_column (fields: sp_row, size [1-12], order)
                    └── sp_instance (fields: sp_column, sp_widget, order)
```

## Standard Layout Patterns

| Pattern | Container Width | Row → Columns |
|---------|----------------|---------------|
| Full-width header | `container-fluid` | 1 row → 1 col-12 |
| Content + sidebar | `container` | 1 row → col-8 + col-4 |
| Three-column equal | `container` | 1 row → col-4 + col-4 + col-4 |
| Nav header (shared) | `container-fluid` | Placed on every page, container order 0 |

## Placement Process

1. Create `sp_container` linked to the page with `order` and `width` (container or container-fluid)
2. Create `sp_row` linked to the container with `order`
3. Create `sp_column` linked to the row with `size` (Bootstrap grid: 1-12) and `order`
4. Create `sp_instance` linked to the column and the widget with `order`

## Navigation Wiring

- Dashboard page: `?id={portal}_home`
- Sub-pages: `?id={portal}_{page_name}`
- Active state: detect via `$sp.getParameter("id")` in the nav widget's server script
- Nav header widget is shared across all pages (placed in container order 0 on each page)
