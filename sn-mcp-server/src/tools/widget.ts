import { z } from "zod";
import type { ServiceNowClient } from "../utils/client.js";

export const widgetTools = (client: ServiceNowClient) => ({
  sn_get_script: {
    description:
      "Get a script artifact by name. Returns the script content and metadata. " +
      "Works with sys_script_include, sys_script, sys_ui_script, sys_script_client.",
    inputSchema: z.object({
      table: z
        .string()
        .describe("Script table (e.g., sys_script_include, sys_script, sys_ui_script, sys_script_client)"),
      name: z.string().describe("Name of the script artifact"),
    }),
    handler: async (input: { table: string; name: string }) => {
      const records = await client.queryRecords(
        input.table,
        `name=${input.name}`,
        ["sys_id", "name", "script", "active", "api_name", "description"],
        1
      );
      if (records.length === 0) {
        return { error: `No ${input.table} record found with name '${input.name}'` };
      }
      return records[0];
    },
  },

  sn_update_script: {
    description:
      "Update the script content of a script artifact by name. " +
      "Finds the record by name, then updates its script field.",
    inputSchema: z.object({
      table: z
        .string()
        .describe("Script table (e.g., sys_script_include, sys_script, sys_ui_script)"),
      name: z.string().describe("Name of the script artifact"),
      script: z.string().describe("New script content"),
    }),
    handler: async (input: { table: string; name: string; script: string }) => {
      const records = await client.queryRecords(
        input.table,
        `name=${input.name}`,
        ["sys_id", "name"],
        1
      );
      if (records.length === 0) {
        return { error: `No ${input.table} record found with name '${input.name}'` };
      }
      const sysId = records[0].sys_id as string;
      return await client.updateRecord(input.table, sysId, { script: input.script });
    },
  },

  sn_list_widgets: {
    description:
      "List Service Portal widgets. Returns widget name, ID, and category. " +
      "Use query to filter (e.g., nameLIKEheader).",
    inputSchema: z.object({
      query: z.string().optional().describe("Encoded query to filter widgets"),
      limit: z.number().optional().default(20).describe("Max widgets to return"),
    }),
    handler: async (input: { query?: string; limit?: number }) => {
      const records = await client.queryRecords(
        "sp_widget",
        input.query,
        ["sys_id", "name", "id", "category"],
        input.limit ?? 20
      );
      return { widgets: records, count: records.length };
    },
  },

  sn_get_widget_by_id: {
    description:
      "Get a Service Portal widget by its widget ID (not sys_id). " +
      "Returns full widget definition including template, CSS, and scripts.",
    inputSchema: z.object({
      widget_id: z
        .string()
        .describe("The widget ID (e.g., csm-unified-portal-header, my-custom-widget)"),
    }),
    handler: async (input: { widget_id: string }) => {
      const records = await client.queryRecords(
        "sp_widget",
        `id=${input.widget_id}`,
        [
          "sys_id",
          "name",
          "id",
          "template",
          "css",
          "client_script",
          "script",
          "link",
          "option_schema",
          "description",
        ],
        1
      );
      if (records.length === 0) {
        return { error: `No widget found with id '${input.widget_id}'` };
      }
      return records[0];
    },
  },
});
