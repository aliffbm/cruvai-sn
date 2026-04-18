import { z } from "zod";
import type { ServiceNowClient } from "../utils/client.js";

export const portalTools = (client: ServiceNowClient) => ({
  sn_build_portal: {
    description:
      "Create a ServiceNow Service Portal (sp_portal) record. " +
      "This defines a new portal instance with its URL suffix, theme, and default pages.",
    inputSchema: z.object({
      name: z.string().describe("Portal display name"),
      url_suffix: z
        .string()
        .describe("URL path suffix (e.g., 'my_portal' -> /sp?id=my_portal)"),
      css: z.string().optional().describe("Custom CSS for the portal"),
      default_page: z
        .string()
        .optional()
        .describe("sys_id of the default landing page (sp_page)"),
      homepage: z
        .string()
        .optional()
        .describe("sys_id of the homepage (sp_page)"),
      theme: z
        .string()
        .optional()
        .describe("sys_id of the sp_theme record to apply"),
    }),
    handler: async (input: {
      name: string;
      url_suffix: string;
      css?: string;
      default_page?: string;
      homepage?: string;
      theme?: string;
    }) => {
      const data: Record<string, unknown> = {
        title: input.name,
        url_suffix: input.url_suffix,
      };
      if (input.css) data.css = input.css;
      if (input.default_page) data.default_page = input.default_page;
      if (input.homepage) data.homepage = input.homepage;
      if (input.theme) data.sp_theme = input.theme;

      const portal = await client.createRecord("sp_portal", data);
      return {
        portal,
        summary: `Created portal "${input.name}" at /${input.url_suffix}`,
      };
    },
  },

  sn_build_portal_page: {
    description:
      "Create a ServiceNow Service Portal page (sp_page). " +
      "Pages are the containers that hold widget instances and define URL routes.",
    inputSchema: z.object({
      title: z.string().describe("Page display title"),
      id: z.string().describe("URL path identifier (e.g., 'home', 'kb_article')"),
      portal_id: z
        .string()
        .optional()
        .describe("sys_id of the portal this page belongs to"),
      internal: z
        .boolean()
        .optional()
        .default(false)
        .describe("Whether this is an internal-only page"),
      css: z.string().optional().describe("Page-level custom CSS"),
    }),
    handler: async (input: {
      title: string;
      id: string;
      portal_id?: string;
      internal?: boolean;
      css?: string;
    }) => {
      const data: Record<string, unknown> = {
        title: input.title,
        id: input.id,
        internal: String(input.internal ?? false),
      };
      if (input.portal_id) data.portal = input.portal_id;
      if (input.css) data.css = input.css;

      const page = await client.createRecord("sp_page", data);
      return {
        page,
        summary: `Created page "${input.title}" with id="${input.id}"`,
      };
    },
  },

  sn_build_widget: {
    description:
      "Create a ServiceNow Service Portal widget (sp_widget) with all " +
      "script components: HTML template, CSS, client script, and server script.",
    inputSchema: z.object({
      name: z.string().describe("Widget display name"),
      id: z.string().describe("Unique widget identifier (e.g., 'my-custom-widget')"),
      template: z.string().describe("HTML body template (Angular 1.x)"),
      css: z.string().describe("Widget SCSS/CSS"),
      client_script: z
        .string()
        .describe("Client-side controller script (Angular 1.x)"),
      server_script: z
        .string()
        .describe("Server-side script (runs in Rhino/GlideRecord context)"),
      link: z
        .string()
        .optional()
        .describe("Angular link function for DOM manipulation"),
      description: z.string().optional().describe("Widget description"),
      data_table: z
        .string()
        .optional()
        .describe("Default data table for the widget"),
    }),
    handler: async (input: {
      name: string;
      id: string;
      template: string;
      css: string;
      client_script: string;
      server_script: string;
      link?: string;
      description?: string;
      data_table?: string;
    }) => {
      const data: Record<string, unknown> = {
        name: input.name,
        id: input.id,
        template: input.template,
        css: input.css,
        client_script: input.client_script,
        script: input.server_script,
      };
      if (input.link) data.link = input.link;
      if (input.description) data.short_description = input.description;
      if (input.data_table) data.data_table = input.data_table;

      const widget = await client.createRecord("sp_widget", data);
      return {
        widget,
        summary: `Created widget "${input.name}" (${input.id})`,
      };
    },
  },

  sn_build_widget_instance: {
    description:
      "Place a widget on a Service Portal page by creating an sp_instance record. " +
      "This binds a widget to a specific page, column, and display order.",
    inputSchema: z.object({
      page_id: z.string().describe("sys_id of the sp_page"),
      widget_id: z.string().describe("sys_id of the sp_widget"),
      column: z.number().describe("Column index on the page (0-based)"),
      order: z.number().describe("Display order within the column"),
      widget_parameters: z
        .record(z.unknown())
        .optional()
        .describe("JSON object of widget instance option values"),
    }),
    handler: async (input: {
      page_id: string;
      widget_id: string;
      column: number;
      order: number;
      widget_parameters?: Record<string, unknown>;
    }) => {
      const data: Record<string, unknown> = {
        sp_page: input.page_id,
        sp_widget: input.widget_id,
        sp_column: String(input.column),
        order: String(input.order),
      };
      if (input.widget_parameters) {
        data.widget_parameters = JSON.stringify(input.widget_parameters);
      }

      const instance = await client.createRecord("sp_instance", data);
      return {
        instance,
        summary: `Placed widget on page (column=${input.column}, order=${input.order})`,
      };
    },
  },

  sn_build_theme: {
    description:
      "Create a ServiceNow Service Portal theme (sp_theme). " +
      "Themes control portal-wide styling, CSS variables, and header/footer widgets.",
    inputSchema: z.object({
      name: z.string().describe("Theme display name"),
      css_variables: z
        .record(z.string())
        .describe("CSS variable key-value pairs (e.g., {'--primary-color': '#1a73e8'})"),
      header_widget: z
        .string()
        .optional()
        .describe("sys_id of the header sp_widget"),
      footer_widget: z
        .string()
        .optional()
        .describe("sys_id of the footer sp_widget"),
      navbar_fixed: z
        .boolean()
        .describe("Whether the navbar should be fixed at the top"),
    }),
    handler: async (input: {
      name: string;
      css_variables: Record<string, string>;
      header_widget?: string;
      footer_widget?: string;
      navbar_fixed: boolean;
    }) => {
      const cssVarsString = Object.entries(input.css_variables)
        .map(([key, value]) => `${key}: ${value};`)
        .join("\n");

      const data: Record<string, unknown> = {
        name: input.name,
        css_variables: cssVarsString,
        navbar_fixed: String(input.navbar_fixed),
      };
      if (input.header_widget) data.header = input.header_widget;
      if (input.footer_widget) data.footer = input.footer_widget;

      const theme = await client.createRecord("sp_theme", data);
      return {
        theme,
        summary: `Created theme "${input.name}" with ${Object.keys(input.css_variables).length} CSS variables`,
      };
    },
  },

  sn_build_css_include: {
    description:
      "Create a ServiceNow Service Portal CSS include (sp_css). " +
      "CSS includes are reusable stylesheets that can be linked to themes or portals.",
    inputSchema: z.object({
      name: z.string().describe("CSS include display name"),
      css: z.string().describe("CSS content (when source is 'inline')"),
      source: z
        .enum(["url", "inline"])
        .describe("Whether CSS is inline content or loaded from a URL"),
      url: z
        .string()
        .optional()
        .describe("External CSS URL (when source is 'url')"),
    }),
    handler: async (input: {
      name: string;
      css: string;
      source: "url" | "inline";
      url?: string;
    }) => {
      const data: Record<string, unknown> = {
        name: input.name,
        css: input.css,
        source: input.source === "url" ? "url" : "local",
      };
      if (input.url) data.url = input.url;

      const cssInclude = await client.createRecord("sp_css", data);
      return {
        css_include: cssInclude,
        summary: `Created CSS include "${input.name}" (source=${input.source})`,
      };
    },
  },

  sn_build_header_footer: {
    description:
      "Configure header and footer widgets for a Service Portal " +
      "by creating or updating an sp_header_footer record.",
    inputSchema: z.object({
      portal_id: z.string().describe("sys_id of the sp_portal"),
      header_widget_id: z
        .string()
        .optional()
        .describe("sys_id of the header sp_widget"),
      footer_widget_id: z
        .string()
        .optional()
        .describe("sys_id of the footer sp_widget"),
    }),
    handler: async (input: {
      portal_id: string;
      header_widget_id?: string;
      footer_widget_id?: string;
    }) => {
      const data: Record<string, unknown> = {
        sp_portal: input.portal_id,
      };
      if (input.header_widget_id) data.sp_header = input.header_widget_id;
      if (input.footer_widget_id) data.sp_footer = input.footer_widget_id;

      const headerFooter = await client.createRecord(
        "sp_header_footer",
        data
      );
      return {
        header_footer: headerFooter,
        summary: `Configured header/footer for portal ${input.portal_id}`,
      };
    },
  },
});
