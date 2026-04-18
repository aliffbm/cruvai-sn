import { z } from "zod";
import type { ServiceNowClient } from "../utils/client.js";

export const updateSetTools = (client: ServiceNowClient) => ({
  sn_create_update_set: {
    description:
      "Create a new update set on the ServiceNow instance. " +
      "All subsequent record changes will be tracked in this update set.",
    inputSchema: z.object({
      name: z.string().describe("Update set name"),
      description: z.string().optional(),
    }),
    handler: async (input: { name: string; description?: string }) => {
      const data: Record<string, unknown> = {
        name: input.name,
        state: "in progress",
      };
      if (input.description) data.description = input.description;

      return await client.createRecord("sys_update_set", data);
    },
  },

  sn_list_update_sets: {
    description: "List update sets, optionally filtered by state.",
    inputSchema: z.object({
      state: z
        .string()
        .optional()
        .default("in progress")
        .describe("Filter by state: 'in progress', 'complete', 'ignore'"),
    }),
    handler: async (input: { state?: string }) => {
      const query = input.state ? `state=${input.state}` : undefined;
      const sets = await client.queryRecords(
        "sys_update_set",
        query,
        ["name", "description", "state", "sys_id", "sys_created_on"],
        50
      );
      return { update_sets: sets, count: sets.length };
    },
  },

  sn_complete_update_set: {
    description: "Mark an update set as complete.",
    inputSchema: z.object({
      sys_id: z.string().describe("sys_id of the update set to complete"),
    }),
    handler: async (input: { sys_id: string }) => {
      return await client.updateRecord("sys_update_set", input.sys_id, {
        state: "complete",
      });
    },
  },
});
