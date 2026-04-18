import { z } from "zod";
import type { ServiceNowClient } from "../utils/client.js";

export const tableTools = (client: ServiceNowClient) => ({
  sn_query: {
    description:
      "Query records from any ServiceNow table using encoded query syntax. " +
      "Supports operators: =, !=, LIKE, STARTSWITH, ENDSWITH, IN, NOTIN, " +
      "ISEMPTY, ISNOTEMPTY, >, >=, <, <=. Join with ^ (AND) or ^OR.",
    inputSchema: z.object({
      table: z.string().describe("ServiceNow table name (e.g., sc_cat_item, sys_script)"),
      query: z.string().optional().describe("Encoded query string (e.g., active=true^category=hardware)"),
      fields: z.array(z.string()).optional().describe("Fields to return (omit for all)"),
      limit: z.number().optional().default(20).describe("Max records to return"),
      offset: z.number().optional().default(0),
    }),
    handler: async (input: {
      table: string;
      query?: string;
      fields?: string[];
      limit?: number;
      offset?: number;
    }) => {
      const records = await client.queryRecords(
        input.table,
        input.query,
        input.fields,
        input.limit ?? 20,
        input.offset ?? 0
      );
      return { records, count: records.length };
    },
  },

  sn_get_record: {
    description: "Get a single ServiceNow record by sys_id.",
    inputSchema: z.object({
      table: z.string(),
      sys_id: z.string().describe("The sys_id of the record"),
      fields: z.array(z.string()).optional(),
    }),
    handler: async (input: { table: string; sys_id: string; fields?: string[] }) => {
      return await client.getRecord(input.table, input.sys_id, input.fields);
    },
  },

  sn_create_record: {
    description:
      "Create a new record on any ServiceNow table. The record will be " +
      "created in the currently active update set.",
    inputSchema: z.object({
      table: z.string(),
      data: z.record(z.unknown()).describe("Field values for the new record"),
    }),
    handler: async (input: { table: string; data: Record<string, unknown> }) => {
      return await client.createRecord(input.table, input.data);
    },
  },

  sn_update_record: {
    description: "Update fields on an existing ServiceNow record.",
    inputSchema: z.object({
      table: z.string(),
      sys_id: z.string(),
      data: z.record(z.unknown()).describe("Fields to update"),
    }),
    handler: async (input: {
      table: string;
      sys_id: string;
      data: Record<string, unknown>;
    }) => {
      return await client.updateRecord(input.table, input.sys_id, input.data);
    },
  },

  sn_delete_record: {
    description: "Delete a ServiceNow record. Use with caution.",
    inputSchema: z.object({
      table: z.string(),
      sys_id: z.string(),
      confirm: z
        .boolean()
        .describe("Must be true to confirm deletion"),
    }),
    handler: async (input: { table: string; sys_id: string; confirm: boolean }) => {
      if (!input.confirm) {
        return { error: "Deletion not confirmed. Set confirm=true." };
      }
      await client.deleteRecord(input.table, input.sys_id);
      return { success: true, deleted: `${input.table}/${input.sys_id}` };
    },
  },
});
