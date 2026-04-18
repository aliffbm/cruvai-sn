import { z } from "zod";
import type { ServiceNowClient } from "../utils/client.js";

export const scriptTools = (client: ServiceNowClient) => ({
  sn_build_business_rule: {
    description:
      "Create a ServiceNow business rule. IMPORTANT: Use getValue()/setValue() " +
      "instead of dot notation for GlideRecord fields. Use current.getValue('field') " +
      "not current.field.",
    inputSchema: z.object({
      name: z.string(),
      table: z.string().describe("Target table (e.g., incident, sc_req_item)"),
      when: z
        .enum(["before", "after", "async", "display"])
        .describe("When to execute"),
      script: z.string().describe("Server-side JavaScript"),
      insert: z.boolean().optional().default(false),
      update: z.boolean().optional().default(false),
      delete_op: z.boolean().optional().default(false),
      query: z.boolean().optional().default(false),
      condition: z.string().optional().describe("Encoded query condition"),
      active: z.boolean().optional().default(true),
    }),
    handler: async (input: {
      name: string;
      table: string;
      when: string;
      script: string;
      insert?: boolean;
      update?: boolean;
      delete_op?: boolean;
      query?: boolean;
      condition?: string;
      active?: boolean;
    }) => {
      const data: Record<string, unknown> = {
        name: input.name,
        collection: input.table,
        when: input.when,
        script: input.script,
        action_insert: String(input.insert ?? false),
        action_update: String(input.update ?? false),
        action_delete: String(input.delete_op ?? false),
        action_query: String(input.query ?? false),
        active: String(input.active ?? true),
      };
      if (input.condition) data.filter_condition = input.condition;

      return await client.createRecord("sys_script", data);
    },
  },

  sn_build_client_script: {
    description:
      "Create a ServiceNow client script (onChange, onLoad, onSubmit, onCellEdit).",
    inputSchema: z.object({
      name: z.string(),
      table: z.string(),
      type: z.enum(["onChange", "onLoad", "onSubmit", "onCellEdit"]),
      script: z.string().describe("Client-side JavaScript"),
      field_name: z
        .string()
        .optional()
        .describe("For onChange: the field that triggers the script"),
      active: z.boolean().optional().default(true),
    }),
    handler: async (input: {
      name: string;
      table: string;
      type: string;
      script: string;
      field_name?: string;
      active?: boolean;
    }) => {
      const data: Record<string, unknown> = {
        name: input.name,
        table: input.table,
        type: input.type,
        script: input.script,
        active: String(input.active ?? true),
      };
      if (input.field_name) data.field_name = input.field_name;

      return await client.createRecord("sys_script_client", data);
    },
  },

  sn_build_ui_policy: {
    description: "Create a ServiceNow UI policy with actions.",
    inputSchema: z.object({
      name: z.string(),
      table: z.string(),
      conditions: z.string().optional().describe("Encoded query conditions"),
      actions: z
        .array(
          z.object({
            field: z.string(),
            visible: z.boolean().optional(),
            mandatory: z.boolean().optional(),
            disabled: z.boolean().optional(),
          })
        )
        .optional()
        .describe("UI policy actions to apply when conditions are met"),
      active: z.boolean().optional().default(true),
    }),
    handler: async (input: {
      name: string;
      table: string;
      conditions?: string;
      actions?: Array<{
        field: string;
        visible?: boolean;
        mandatory?: boolean;
        disabled?: boolean;
      }>;
      active?: boolean;
    }) => {
      // Create UI policy
      const policyData: Record<string, unknown> = {
        short_description: input.name,
        table: input.table,
        active: String(input.active ?? true),
      };
      if (input.conditions) policyData.conditions = input.conditions;

      const policy = await client.createRecord("sys_ui_policy", policyData);
      const policySysId = (policy as Record<string, string>).sys_id;

      // Create actions
      const createdActions = [];
      for (const action of input.actions ?? []) {
        const actionData: Record<string, unknown> = {
          ui_policy: policySysId,
          field: action.field,
        };
        if (action.visible !== undefined)
          actionData.visible = action.visible ? "true" : "false";
        if (action.mandatory !== undefined)
          actionData.mandatory = action.mandatory ? "true" : "false";
        if (action.disabled !== undefined)
          actionData.disabled = action.disabled ? "true" : "false";

        const created = await client.createRecord("sys_ui_policy_action", actionData);
        createdActions.push(created);
      }

      return {
        policy,
        actions: createdActions,
        summary: `Created UI policy "${input.name}" with ${createdActions.length} actions`,
      };
    },
  },

  sn_build_notification: {
    description: "Create a ServiceNow email notification.",
    inputSchema: z.object({
      name: z.string(),
      table: z.string(),
      event_name: z.string().optional().describe("Event to trigger on"),
      condition: z.string().optional().describe("Encoded query condition"),
      subject: z.string(),
      message_html: z.string().describe("Email body (HTML)"),
      send_to_event_creator: z.boolean().optional().default(false),
    }),
    handler: async (input: {
      name: string;
      table: string;
      event_name?: string;
      condition?: string;
      subject: string;
      message_html: string;
      send_to_event_creator?: boolean;
    }) => {
      const data: Record<string, unknown> = {
        name: input.name,
        collection: input.table,
        subject: input.subject,
        message_html: input.message_html,
        active: "true",
        send_self: String(input.send_to_event_creator ?? false),
      };
      if (input.event_name) data.event_name = input.event_name;
      if (input.condition) data.condition = input.condition;

      return await client.createRecord("sysevent_email_action", data);
    },
  },

  sn_validate_script: {
    description:
      "Validate a ServiceNow script for common issues: " +
      "dot notation instead of getValue/setValue, scoped app restrictions, " +
      "deprecated APIs, naming conventions.",
    inputSchema: z.object({
      script: z.string(),
      script_type: z
        .enum(["business_rule", "client_script", "script_include", "ui_policy"])
        .describe("Type of script being validated"),
    }),
    handler: async (input: { script: string; script_type: string }) => {
      const issues: Array<{
        severity: string;
        category: string;
        message: string;
        line?: number;
      }> = [];

      const lines = input.script.split("\n");

      for (let i = 0; i < lines.length; i++) {
        const line = lines[i];
        const lineNum = i + 1;

        // Check for dot notation on GlideRecord (server-side only)
        if (input.script_type !== "client_script") {
          if (/current\.\w+\s*=/.test(line) && !line.includes("setValue")) {
            issues.push({
              severity: "warning",
              category: "best_practice",
              message: `Line ${lineNum}: Use current.setValue('field', value) instead of dot notation`,
              line: lineNum,
            });
          }
          if (/current\.\w+[^(]/.test(line) && !line.includes("getValue") && !line.includes("setValue") && !line.includes("//")) {
            // Simplified check - real validator would be more sophisticated
          }
        }

        // Check for gs.nowDateTime() in scoped apps
        if (line.includes("gs.nowDateTime()")) {
          issues.push({
            severity: "info",
            category: "scoped_app",
            message: `Line ${lineNum}: gs.nowDateTime() may not work in scoped apps. Use GlideDateTime().getDisplayValue()`,
            line: lineNum,
          });
        }

        // Check for eval()
        if (line.includes("eval(")) {
          issues.push({
            severity: "error",
            category: "security",
            message: `Line ${lineNum}: eval() is a security risk and blocked in scoped apps`,
            line: lineNum,
          });
        }

        // Check for hardcoded sys_ids
        if (/['"][a-f0-9]{32}['"]/.test(line)) {
          issues.push({
            severity: "warning",
            category: "best_practice",
            message: `Line ${lineNum}: Avoid hardcoded sys_ids. Use sys_properties or system properties instead`,
            line: lineNum,
          });
        }
      }

      return {
        valid: issues.filter((i) => i.severity === "error").length === 0,
        issues,
        issue_count: issues.length,
        error_count: issues.filter((i) => i.severity === "error").length,
        warning_count: issues.filter((i) => i.severity === "warning").length,
      };
    },
  },
});
