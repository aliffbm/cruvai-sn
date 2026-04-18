"use client";

import { useState } from "react";

const KB_SECTIONS = [
  {
    title: "Documentation",
    path: "docs",
    items: [
      { name: "Channel Routing Guide", file: "channel-routing.md", desc: "Which deployment channel to use for each SN operation" },
      { name: "CSM Portal Architecture", file: "csm-portal-architecture.md", desc: "Deep dive into OOB CSM & Business Portal patterns" },
      { name: "Figma to ServiceNow", file: "figma-to-servicenow.md", desc: "Figma MCP tools and design-to-SN mapping" },
      { name: "sn-scriptsync Agent API", file: "sn-scriptsync-agent-api.md", desc: "Complete Agent API reference for file-based sync" },
      { name: "How to Use", file: "HOW-TO-USE.md", desc: "Step-by-step guide for building portals" },
    ],
  },
  {
    title: "Patterns",
    path: "patterns",
    items: [
      { name: "SP Layout Hierarchy", file: "sp-layout-hierarchy.md", desc: "Critical: page → container → row → column → instance" },
      { name: "Widget Code Patterns", file: "widget-code-patterns.md", desc: "Server script, client script, and HTML template patterns" },
      { name: "Multi-Channel Deployment", file: "multi-channel-deployment.md", desc: "Decision tree for REST API vs sn-scriptsync vs SDK" },
    ],
  },
  {
    title: "Design Maps",
    path: "docs/design-maps",
    items: [
      { name: "Zayo Design Map", file: "zayo-design-map.md", desc: "Figma → SN component mapping for Zayo V2 portal" },
      { name: "Zayo OOB Mapping", file: "zayo-oob-mapping.md", desc: "OOB widget reuse analysis for Zayo V2" },
      { name: "Zayo V2 Executive Summary", file: "zayo-v2-executive-summary.md", desc: "Portal overview and architecture" },
    ],
  },
  {
    title: "Reference",
    path: "reference",
    items: [
      { name: "GrapesJS Component Reference", file: "grapesjs/component-reference.html", desc: "47 registered component types for Content Publishing" },
      { name: "sn-scriptsync File Structure", file: "sn-scriptsync/agentinstructions.md", desc: "File naming conventions and _map.json handling" },
      { name: "SN Server API Types", file: "autocomplete/server.d.ts", desc: "GlideRecord, GlideQuery, REST API type definitions (4K+ lines)" },
      { name: "SN Client API Types", file: "autocomplete/client.d.ts", desc: "g_form, g_navigation, spUtil, AngularJS scope" },
    ],
  },
];

export default function KnowledgeBasePage() {
  const [expandedSection, setExpandedSection] = useState<string | null>("Documentation");
  const [search, setSearch] = useState("");

  const filtered = KB_SECTIONS.map((section) => ({
    ...section,
    items: section.items.filter(
      (item) =>
        item.name.toLowerCase().includes(search.toLowerCase()) ||
        item.desc.toLowerCase().includes(search.toLowerCase())
    ),
  })).filter((section) => section.items.length > 0);

  return (
    <div>
      <div className="mb-6">
        <h1 className="text-2xl font-bold">Knowledge Base</h1>
        <p className="text-sm text-[var(--muted-foreground)] mt-1">
          ServiceNow development patterns, documentation, and reference material
        </p>
      </div>

      <input
        type="text"
        placeholder="Search knowledge base..."
        value={search}
        onChange={(e) => setSearch(e.target.value)}
        className="mb-6 w-full rounded-lg border border-[var(--border)] bg-[var(--background)] px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-[var(--ring)]"
      />

      <div className="space-y-4">
        {filtered.map((section) => (
          <div key={section.title} className="rounded-lg border border-[var(--border)] bg-[var(--card)]">
            <button
              onClick={() =>
                setExpandedSection(expandedSection === section.title ? null : section.title)
              }
              className="w-full flex items-center justify-between px-4 py-3 text-left"
            >
              <div className="flex items-center gap-2">
                <h2 className="font-medium">{section.title}</h2>
                <span className="rounded-full bg-[var(--secondary)] px-2 py-0.5 text-xs text-[var(--muted-foreground)]">
                  {section.items.length}
                </span>
              </div>
              <span className="text-[var(--muted-foreground)] text-sm">
                {expandedSection === section.title ? "−" : "+"}
              </span>
            </button>

            {expandedSection === section.title && (
              <div className="border-t border-[var(--border)] px-4 py-2">
                {section.items.map((item) => (
                  <div
                    key={item.file}
                    className="flex items-start justify-between py-3 border-b border-[var(--border)] last:border-0"
                  >
                    <div>
                      <h3 className="text-sm font-medium">{item.name}</h3>
                      <p className="text-xs text-[var(--muted-foreground)] mt-0.5">{item.desc}</p>
                      <p className="text-xs text-[var(--muted-foreground)] mt-1 font-mono opacity-50">
                        knowledge-base/{section.path}/{item.file}
                      </p>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        ))}
      </div>

      {filtered.length === 0 && (
        <p className="text-sm text-[var(--muted-foreground)] text-center py-8">
          No matching documents found.
        </p>
      )}
    </div>
  );
}
