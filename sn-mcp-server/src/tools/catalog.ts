import { z } from "zod";
import type { ServiceNowClient } from "../utils/client.js";
import { SN_VARIABLE_TYPES } from "../utils/types.js";

export const catalogTools = (client: ServiceNowClient) => ({
  sn_build_catalog_item: {
    description:
      "Create a complete ServiceNow catalog item with variables. " +
      "This is a high-level builder that creates the sc_cat_item record " +
      "and all associated item_option_new (variable) records.",
    inputSchema: z.object({
      name: z.string().describe("Catalog item name"),
      short_description: z.string().describe("Brief description"),
      description: z.string().optional().describe("Full HTML description"),
      category: z.string().optional().describe("sys_id of the catalog category"),
      variables: z
        .array(
          z.object({
            name: z.string().describe("Variable name (no spaces, e.g., laptop_model)"),
            question_text: z.string().describe("Label shown to the user"),
            type: z
              .string()
              .optional()
              .default("6")
              .describe(
                "Variable type code: 6=single line, 7=multi line, 1=checkbox, " +
                "2=select box, 8=reference, 9=date, 10=datetime"
              ),
            mandatory: z.boolean().optional().default(false),
            default_value: z.string().optional(),
            choices: z
              .array(
                z.object({
                  text: z.string(),
                  value: z.string(),
                  order: z.number().optional(),
                })
              )
              .optional()
              .describe("For select box (type=2): choice options"),
            reference_table: z.string().optional().describe("For reference (type=8): target table"),
          })
        )
        .optional()
        .default([]),
    }),
    handler: async (input: {
      name: string;
      short_description: string;
      description?: string;
      category?: string;
      variables?: Array<{
        name: string;
        question_text: string;
        type?: string;
        mandatory?: boolean;
        default_value?: string;
        choices?: Array<{ text: string; value: string; order?: number }>;
        reference_table?: string;
      }>;
    }) => {
      // 1. Create the catalog item
      const catItemData: Record<string, unknown> = {
        name: input.name,
        short_description: input.short_description,
        active: "true",
      };
      if (input.description) catItemData.description = input.description;
      if (input.category) catItemData.category = input.category;

      const catItem = await client.createRecord("sc_cat_item", catItemData);
      const catItemSysId = (catItem as Record<string, string>).sys_id;

      // 2. Create variables
      const createdVariables = [];
      for (let i = 0; i < (input.variables?.length ?? 0); i++) {
        const v = input.variables![i];
        const varData: Record<string, unknown> = {
          cat_item: catItemSysId,
          name: v.name,
          question_text: v.question_text,
          type: v.type || "6",
          mandatory: String(v.mandatory ?? false),
          order: String((i + 1) * 100),
        };
        if (v.default_value) varData.default_value = v.default_value;
        if (v.reference_table) varData.reference = v.reference_table;

        const created = await client.createRecord("item_option_new", varData);
        createdVariables.push(created);

        // 3. Create choices for select box variables
        if (v.type === "2" && v.choices) {
          for (let j = 0; j < v.choices.length; j++) {
            const choice = v.choices[j];
            await client.createRecord("question_choice", {
              question: (created as Record<string, string>).sys_id,
              text: choice.text,
              value: choice.value,
              order: String(choice.order ?? (j + 1) * 100),
            });
          }
        }
      }

      return {
        catalog_item: catItem,
        variables: createdVariables,
        summary: `Created catalog item "${input.name}" with ${createdVariables.length} variables`,
      };
    },
  },

  sn_build_record_producer: {
    description:
      "Create a ServiceNow record producer (form-based record creation " +
      "accessible from the service catalog).",
    inputSchema: z.object({
      name: z.string(),
      table: z.string().describe("Target table for created records"),
      short_description: z.string(),
      script: z.string().optional().describe("Server-side script to run on submission"),
    }),
    handler: async (input: {
      name: string;
      table: string;
      short_description: string;
      script?: string;
    }) => {
      const data: Record<string, unknown> = {
        name: input.name,
        table_name: input.table,
        short_description: input.short_description,
        active: "true",
      };
      if (input.script) data.script = input.script;

      return await client.createRecord("sc_cat_item_producer", data);
    },
  },
});
