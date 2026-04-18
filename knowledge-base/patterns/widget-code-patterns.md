# ServiceNow Widget Code Patterns

## Server Script (Always IIFE)

```javascript
(function() {
    // Define output data
    data.title = "Widget Title";

    // Query data
    var gr = new GlideRecord('table_name');
    gr.addQuery('active', true);
    gr.orderBy('name');
    gr.setLimit(20);
    gr.query();

    data.items = [];
    while (gr.next()) {
        data.items.push({
            sys_id: gr.getUniqueValue(),
            name: gr.getValue('name'),
            description: gr.getValue('description')
        });
    }

    // Handle client input
    if (input) {
        // Process form submission or button click
    }
})()
```

## Client Script (Always function($scope))

```javascript
function($scope) {
    var c = this;

    c.onClick = function(item) {
        c.data.selectedItem = item;
        c.server.update().then(function(response) {
            c.data = response.data;
        });
    };
}
```

## HTML Template (Bootstrap 3 + AngularJS 1.x)

```html
<div class="panel panel-default">
    <div class="panel-heading">
        <h3 class="panel-title">{{c.data.title}}</h3>
    </div>
    <div class="panel-body">
        <div class="list-group">
            <a ng-repeat="item in c.data.items"
               class="list-group-item"
               ng-click="c.onClick(item)">
                <h4 class="list-group-item-heading">{{item.name}}</h4>
                <p class="list-group-item-text">{{item.description}}</p>
            </a>
        </div>
    </div>
</div>
```

## Server Script Patterns by Widget Type

| Widget Type | Pattern | Key APIs |
|-------------|---------|----------|
| Stat cards | `GlideAggregate` with `addAggregate("COUNT")` | `ga.getAggregate("COUNT")` |
| Data tables | `GlideRecord` with `.setLimit()`, account-scoped | `gr.addQuery()`, `gr.orderByDesc()` |
| Detail pages | Load single record by sys_id | `$sp.getParameter("sys_id")` |
| Create forms | Embed Record Producer widget | `$sp.getWidget("widget-sc-cat-item-v2", {sys_id: rpId})` |
| KB articles | Query published articles | `gr.addQuery("workflow_state", "published")` |
| Search | Embed OOB search widget | `$sp.getWidget("typeahead-search")` |

## Conventions

- Widget IDs: lowercase with hyphens (`my-custom-widget`)
- Server scripts: always IIFE `(function() { ... })()`
- Client scripts: always `function($scope) { var c = this; ... }`
- Client → server calls: `c.server.update()` (read-write) or `c.server.get()` (read-only)
- URL params: `$sp.getParameter('param_name')` in server script
- Bootstrap 3 grid: `col-xs-*`, `col-sm-*`, `col-md-*`, `col-lg-*` (NOT Bootstrap 4/5)
- Embed other widgets: `$sp.getWidget("widget-id", options)` in server script
