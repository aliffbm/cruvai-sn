#!/usr/bin/env node

import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { ServiceNowClient } from "./utils/client.js";
import { tableTools } from "./tools/table.js";
import { catalogTools } from "./tools/catalog.js";
import { scriptTools } from "./tools/script.js";
import { schemaTools } from "./tools/schema.js";
import { updateSetTools } from "./tools/update-set.js";
import { portalTools } from "./tools/portal.js";
import { widgetTools } from "./tools/widget.js";
import { csmTools } from "./tools/csm.js";

const server = new McpServer({
  name: "servicenow",
  version: "0.1.0",
});

// Initialize ServiceNow client from environment
const client = ServiceNowClient.fromEnv();

// Register all tool groups
const allTools = {
  ...tableTools(client),
  ...catalogTools(client),
  ...scriptTools(client),
  ...schemaTools(client),
  ...updateSetTools(client),
  ...portalTools(client),
  ...widgetTools(client),
  ...csmTools(client),
};

// Register each tool with the MCP server
for (const [name, tool] of Object.entries(allTools)) {
  server.tool(name, tool.description, tool.inputSchema, async (input: Record<string, unknown>) => {
    try {
      const result = await (tool.handler as (input: Record<string, unknown>) => Promise<unknown>)(input);
      return {
        content: [{ type: "text" as const, text: JSON.stringify(result, null, 2) }],
      };
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      return {
        content: [{ type: "text" as const, text: `Error: ${message}` }],
        isError: true,
      };
    }
  });
}

// Start the server
async function main() {
  const transport = new StdioServerTransport();
  await server.connect(transport);
  console.error("ServiceNow MCP Server running on stdio");
}

main().catch((error) => {
  console.error("Failed to start MCP server:", error);
  process.exit(1);
});
