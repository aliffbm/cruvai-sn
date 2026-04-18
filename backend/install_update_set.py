"""
Create a Scripted REST API on the ServiceNow instance that allows our agent
to write to html_template fields (sp_widget.template) which the Table API
cannot set.

This script creates:
1. A Scripted REST API service: 'Cruvai Agent API'
2. A resource endpoint: POST /api/x_cruvai/agent/widget_template
   - Sets the template, css, client_script, and server script on a widget
   - Bypasses the html_template field restriction

Run once per instance to install.
"""

import asyncio
import sys
from app.connectors.base import BaseServiceNowConnector

# The server-side script for the Scripted REST endpoint
WIDGET_TEMPLATE_SCRIPT = r"""(function process(/*RESTAPIRequest*/ request, /*RESTAPIResponse*/ response) {
    var body = request.body.data;
    var widgetId = body.widget_id || '';
    var sysId = body.sys_id || '';

    if (!widgetId && !sysId) {
        response.setStatus(400);
        return {error: 'widget_id or sys_id required'};
    }

    var gr = new GlideRecord('sp_widget');
    if (sysId) {
        gr.get(sysId);
    } else {
        gr.addQuery('id', widgetId);
        gr.query();
        gr.next();
    }

    if (!gr.isValidRecord()) {
        response.setStatus(404);
        return {error: 'Widget not found'};
    }

    // Set fields - html_template type works via GlideRecord
    if (body.template !== undefined) gr.setValue('template', body.template);
    if (body.css !== undefined) gr.setValue('css', body.css);
    if (body.client_script !== undefined) gr.setValue('client_script', body.client_script);
    if (body.server_script !== undefined) gr.setValue('script', body.server_script);
    if (body.name !== undefined) gr.setValue('name', body.name);

    gr.update();

    return {
        success: true,
        sys_id: gr.getUniqueValue(),
        widget_id: gr.getValue('id'),
        name: gr.getValue('name')
    };
})(request, response);"""

# Script for bulk operations
BULK_WIDGET_SCRIPT = r"""(function process(/*RESTAPIRequest*/ request, /*RESTAPIResponse*/ response) {
    var body = request.body.data;
    var widgets = body.widgets || [];
    var results = [];

    for (var i = 0; i < widgets.length; i++) {
        var w = widgets[i];
        var gr = new GlideRecord('sp_widget');

        if (w.sys_id) {
            gr.get(w.sys_id);
        } else if (w.widget_id) {
            gr.addQuery('id', w.widget_id);
            gr.query();
            gr.next();
        }

        if (gr.isValidRecord()) {
            if (w.template !== undefined) gr.setValue('template', w.template);
            if (w.css !== undefined) gr.setValue('css', w.css);
            if (w.client_script !== undefined) gr.setValue('client_script', w.client_script);
            if (w.server_script !== undefined) gr.setValue('script', w.server_script);
            gr.update();
            results.push({success: true, widget_id: gr.getValue('id'), sys_id: gr.getUniqueValue()});
        } else {
            results.push({success: false, widget_id: w.widget_id || w.sys_id, error: 'Not found'});
        }
    }

    return {results: results, count: results.length};
})(request, response);"""

# Script for setting portal homepage
PORTAL_UPDATE_SCRIPT = r"""(function process(/*RESTAPIRequest*/ request, /*RESTAPIResponse*/ response) {
    var body = request.body.data;
    var portalId = body.portal_sys_id || '';

    if (!portalId) {
        response.setStatus(400);
        return {error: 'portal_sys_id required'};
    }

    var gr = new GlideRecord('sp_portal');
    gr.get(portalId);

    if (!gr.isValidRecord()) {
        response.setStatus(404);
        return {error: 'Portal not found'};
    }

    if (body.homepage !== undefined) gr.setValue('homepage', body.homepage);
    if (body.sp_theme !== undefined) gr.setValue('sp_theme', body.sp_theme);
    if (body.css !== undefined) gr.setValue('css', body.css);

    gr.update();

    return {
        success: true,
        sys_id: gr.getUniqueValue(),
        title: gr.getValue('title')
    };
})(request, response);"""


async def install(instance_url: str, username: str, password: str):
    c = BaseServiceNowConnector(instance_url, username, password)

    print("Installing Cruvai Agent API on ServiceNow instance...")
    print(f"Instance: {instance_url}")

    # Step 1: Create the Scripted REST Service
    print("\n1. Creating Scripted REST Service...")
    try:
        service = await c.create_record("sys_ws_definition", {
            "name": "Cruvai Agent API",
            "short_description": "REST API for Cruvai AI Agent operations that require server-side GlideRecord access",
            "is_active": "true",
            "enforce_acl": "true",
        })
        service_id = service.get("sys_id", "")
        print(f"   Created: {service_id}")
    except Exception as e:
        # Might already exist
        print(f"   Error (may already exist): {e}")
        existing = await c.query_records(
            "sys_ws_definition", "name=Cruvai Agent API", ["sys_id"], limit=1
        )
        if existing:
            service_id = existing[0]["sys_id"]
            print(f"   Using existing: {service_id}")
        else:
            print("   FAILED - cannot continue")
            return

    # Step 2: Create Widget Template endpoint
    print("\n2. Creating widget_template endpoint...")
    try:
        endpoint1 = await c.create_record("sys_ws_operation", {
            "web_service_definition": service_id,
            "name": "Update Widget Template",
            "http_method": "POST",
            "relative_path": "/widget_template",
            "operation_script": WIDGET_TEMPLATE_SCRIPT,
            "is_active": "true",
            "enforce_acl": "true",
            "requires_acl_authorization": "true",
        })
        print(f"   Created: {endpoint1.get('sys_id', '')}")
    except Exception as e:
        print(f"   Error: {e}")

    # Step 3: Create Bulk Widget endpoint
    print("\n3. Creating bulk_widgets endpoint...")
    try:
        endpoint2 = await c.create_record("sys_ws_operation", {
            "web_service_definition": service_id,
            "name": "Bulk Update Widgets",
            "http_method": "POST",
            "relative_path": "/bulk_widgets",
            "operation_script": BULK_WIDGET_SCRIPT,
            "is_active": "true",
            "enforce_acl": "true",
        })
        print(f"   Created: {endpoint2.get('sys_id', '')}")
    except Exception as e:
        print(f"   Error: {e}")

    # Step 4: Create Portal Update endpoint
    print("\n4. Creating portal_update endpoint...")
    try:
        endpoint3 = await c.create_record("sys_ws_operation", {
            "name": "Update Portal",
            "web_service_definition": service_id,
            "http_method": "POST",
            "relative_path": "/portal_update",
            "operation_script": PORTAL_UPDATE_SCRIPT,
            "is_active": "true",
            "enforce_acl": "true",
        })
        print(f"   Created: {endpoint3.get('sys_id', '')}")
    except Exception as e:
        print(f"   Error: {e}")

    print("\n" + "=" * 60)
    print("Installation complete!")
    print(f"\nEndpoints available at:")
    print(f"  POST {instance_url}/api/x_snc_global/cruvai_agent_api/widget_template")
    print(f"  POST {instance_url}/api/x_snc_global/cruvai_agent_api/bulk_widgets")
    print(f"  POST {instance_url}/api/x_snc_global/cruvai_agent_api/portal_update")
    print(f"\nNote: The namespace may vary. Check the Scripted REST API record for the actual path.")

    await c.close()


if __name__ == "__main__":
    if len(sys.argv) < 4:
        print("Usage: python install_update_set.py <instance_url> <username> <password>")
        sys.exit(1)
    asyncio.run(install(sys.argv[1], sys.argv[2], sys.argv[3]))
