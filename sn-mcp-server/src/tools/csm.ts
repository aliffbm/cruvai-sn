import { z } from "zod";
import type { ServiceNowClient } from "../utils/client.js";

export const csmTools = (client: ServiceNowClient) => ({
  sn_list_cases: {
    description:
      "List CSM (Customer Service Management) cases. " +
      "Queries sn_customerservice_case with common fields.",
    inputSchema: z.object({
      query: z
        .string()
        .optional()
        .describe("Encoded query (e.g., state=1^priority=2)"),
      limit: z.number().optional().default(10).describe("Max cases to return"),
    }),
    handler: async (input: { query?: string; limit?: number }) => {
      const records = await client.queryRecords(
        "sn_customerservice_case",
        input.query,
        [
          "sys_id",
          "number",
          "short_description",
          "state",
          "priority",
          "contact",
          "account",
        ],
        input.limit ?? 10
      );
      return { cases: records, count: records.length };
    },
  },

  sn_list_orders: {
    description:
      "List CSM orders. Queries sn_csm_order with common fields.",
    inputSchema: z.object({
      query: z
        .string()
        .optional()
        .describe("Encoded query to filter orders"),
      limit: z.number().optional().default(10).describe("Max orders to return"),
    }),
    handler: async (input: { query?: string; limit?: number }) => {
      const records = await client.queryRecords(
        "sn_csm_order",
        input.query,
        [
          "sys_id",
          "number",
          "short_description",
          "state",
          "stage",
          "account",
        ],
        input.limit ?? 10
      );
      return { orders: records, count: records.length };
    },
  },

  sn_test_connection: {
    description:
      "Test the connection to the ServiceNow instance. " +
      "Returns instance URL, authenticated user, and build tag.",
    inputSchema: z.object({}),
    handler: async () => {
      const records = await client.queryRecords(
        "sys_properties",
        "name=glide.buildtag.last",
        ["name", "value"],
        1
      );
      const build = records.length > 0 ? (records[0].value as string) : "unknown";
      return {
        status: "connected",
        instance: process.env.SN_INSTANCE_URL || "unknown",
        user: process.env.SN_USERNAME || "unknown",
        build,
      };
    },
  },
});
