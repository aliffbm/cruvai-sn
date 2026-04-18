import { z } from "zod";
import type { ServiceNowClient } from "../utils/client.js";

export const schemaTools = (client: ServiceNowClient) => ({
  sn_get_schema: {
    description:
      "Get the schema (field definitions) for a ServiceNow table. " +
      "Returns column names, types, labels, and whether they are mandatory.",
    inputSchema: z.object({
      table: z.string().describe("Table name to get schema for"),
    }),
    handler: async (input: { table: string }) => {
      const records = await client.queryRecords(
        "sys_dictionary",
        `name=${input.table}^internal_type!=collection`,
        ["element", "column_label", "internal_type", "mandatory", "max_length", "reference"],
        500
      );
      return {
        table: input.table,
        fields: records.map((r: Record<string, unknown>) => ({
          name: r.element,
          label: r.column_label,
          type: r.internal_type,
          mandatory: r.mandatory,
          max_length: r.max_length,
          reference: r.reference,
        })),
        field_count: records.length,
      };
    },
  },

  sn_list_scopes: {
    description: "List all application scopes on the ServiceNow instance.",
    inputSchema: z.object({}),
    handler: async () => {
      const scopes = await client.queryRecords(
        "sys_scope",
        undefined,
        ["scope", "name", "sys_id", "version"],
        100
      );
      return { scopes, count: scopes.length };
    },
  },

  sn_list_tables: {
    description: "Search for tables on the ServiceNow instance by name pattern.",
    inputSchema: z.object({
      search: z.string().describe("Table name pattern to search (e.g., 'incident', 'sc_cat')"),
    }),
    handler: async (input: { search: string }) => {
      const tables = await client.queryRecords(
        "sys_db_object",
        `name LIKE ${input.search}`,
        ["name", "label", "super_class", "sys_id"],
        50
      );
      return { tables, count: tables.length };
    },
  },
});
