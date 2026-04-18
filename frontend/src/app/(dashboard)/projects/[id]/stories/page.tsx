"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { api } from "@/lib/api";

export default function StoriesPage() {
  const { id: projectId } = useParams<{ id: string }>();
  const [stories, setStories] = useState<any[]>([]);
  const [showCreate, setShowCreate] = useState(false);
  const [agents, setAgents] = useState<any[]>([]);
  const [instances, setInstances] = useState<any[]>([]);
  const [launchingStory, setLaunchingStory] = useState<any>(null);
  const [launchAgent, setLaunchAgent] = useState("");
  const [launchInstance, setLaunchInstance] = useState("");
  const [newStory, setNewStory] = useState({
    title: "",
    description: "",
    acceptance_criteria: "",
    priority: 3,
  });
  const [showFigmaImport, setShowFigmaImport] = useState(false);
  const [figmaUrl, setFigmaUrl] = useState("");
  const [figmaConnectors, setFigmaConnectors] = useState<any[]>([]);
  const [selectedConnector, setSelectedConnector] = useState("");
  const [portalType, setPortalType] = useState("");
  const [importing, setImporting] = useState(false);
  const [importResult, setImportResult] = useState<any>(null);

  useEffect(() => {
    if (!projectId) return;
    api.listStories(projectId).then(setStories).catch(console.error);
    // Load agents and instances for the launcher
    fetch("/api/v1/instances", {
      headers: { Authorization: `Bearer ${api.getToken()}` },
    })
      .then((r) => r.json())
      .then(setInstances)
      .catch(console.error);
  }, [projectId]);

  // Load Figma connectors when import modal opens and default to the
  // project's configured Figma connector if any.
  useEffect(() => {
    if (showFigmaImport && figmaConnectors.length === 0) {
      Promise.all([
        api.listConnectors(),
        api.getProject(projectId).catch(() => null),
      ]).then(([connectors, proj]) => {
        const figmas = connectors.filter((c: any) => c.platform === "figma");
        setFigmaConnectors(figmas);
        if (!selectedConnector) {
          const projectDefault = proj?.figma_connector_id;
          if (projectDefault && figmas.some((c: any) => c.id === projectDefault)) {
            setSelectedConnector(projectDefault);
          } else if (figmas.length === 1) {
            setSelectedConnector(figmas[0].id);
          }
        }
      }).catch(console.error);
    }
  }, [showFigmaImport, projectId, selectedConnector, figmaConnectors.length]);

  async function handleFigmaImport() {
    if (!figmaUrl || !selectedConnector) return;
    setImporting(true);
    setImportResult(null);
    try {
      const result = await api.importFigmaStories(projectId, {
        figma_url: figmaUrl,
        connector_id: selectedConnector,
        portal_type: portalType || undefined,
      });
      setImportResult(result);
      // Refresh stories list
      const updated = await api.listStories(projectId);
      setStories(updated);
      setFigmaUrl("");
      setSelectedConnector("");
      setPortalType("");
    } catch (e: any) {
      setImportResult({ error: e.message });
    }
    setImporting(false);
  }

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    const created = await api.createStory(projectId, newStory);
    setStories([...stories, created]);
    setShowCreate(false);
    setNewStory({ title: "", description: "", acceptance_criteria: "", priority: 3 });
  }

  async function handleLaunch() {
    if (!launchAgent || !launchInstance || !launchingStory) return;
    try {
      const job = await api.createJob(projectId, {
        agent_id: launchAgent,
        story_id: launchingStory.id,
        instance_id: launchInstance,
      });
      // Navigate to the job detail page
      window.location.href = `/projects/${projectId}/jobs/${job.id}`;
    } catch (err: any) {
      alert("Failed to launch agent: " + err.message);
    }
  }

  // Load agent definitions when launcher opens
  useEffect(() => {
    if (launchingStory && agents.length === 0) {
      fetch("/api/v1/agents", {
        headers: { Authorization: `Bearer ${api.getToken()}` },
      })
        .then((r) => r.json())
        .then((data) => {
          setAgents(Array.isArray(data) ? data : []);
        })
        .catch(() => {
          // Agents endpoint might not exist yet, use fallback
          setAgents([]);
        });
    }
  }, [launchingStory]);

  const statusColors: Record<string, string> = {
    backlog: "bg-zinc-700",
    ready: "bg-blue-500/20 text-blue-400",
    in_progress: "bg-yellow-500/20 text-yellow-400",
    review: "bg-purple-500/20 text-purple-400",
    testing: "bg-orange-500/20 text-orange-400",
    done: "bg-green-500/20 text-green-400",
  };

  const priorityLabels: Record<number, string> = {
    1: "Critical",
    2: "High",
    3: "Medium",
    4: "Low",
  };

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold">User Stories</h1>
          <p className="text-sm text-[var(--muted-foreground)] mt-1">
            Create stories and launch AI agents to build ServiceNow solutions
          </p>
        </div>
        <div className="flex gap-2">
          <button
            onClick={() => setShowFigmaImport(true)}
            className="rounded-lg border border-[var(--border)] px-4 py-2 text-sm font-medium hover:bg-[var(--secondary)]"
          >
            Import from Figma
          </button>
          <button
            onClick={() => setShowCreate(true)}
            className="rounded-lg bg-[var(--primary)] px-4 py-2 text-sm font-medium text-[var(--primary-foreground)] hover:opacity-90"
          >
            + New Story
          </button>
        </div>
      </div>

      {/* Create Story Form */}
      {showCreate && (
        <form
          onSubmit={handleCreate}
          className="mb-6 rounded-lg border border-[var(--border)] bg-[var(--card)] p-5 space-y-4"
        >
          <div>
            <label className="block text-sm font-medium mb-1.5">Title</label>
            <input
              type="text"
              value={newStory.title}
              onChange={(e) => setNewStory({ ...newStory, title: e.target.value })}
              placeholder="e.g., Laptop Request Catalog Item"
              className="w-full rounded-lg border border-[var(--border)] bg-[var(--background)] px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[var(--ring)]"
              required
            />
          </div>
          <div>
            <label className="block text-sm font-medium mb-1.5">Description</label>
            <textarea
              value={newStory.description}
              onChange={(e) => setNewStory({ ...newStory, description: e.target.value })}
              placeholder="Describe what needs to be built on ServiceNow..."
              className="w-full rounded-lg border border-[var(--border)] bg-[var(--background)] px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[var(--ring)]"
              rows={3}
            />
          </div>
          <div>
            <label className="block text-sm font-medium mb-1.5">Acceptance Criteria</label>
            <textarea
              value={newStory.acceptance_criteria}
              onChange={(e) =>
                setNewStory({ ...newStory, acceptance_criteria: e.target.value })
              }
              placeholder="- Catalog item appears in the service catalog&#10;- Has dropdown for laptop model&#10;- Business rule auto-sets priority..."
              className="w-full rounded-lg border border-[var(--border)] bg-[var(--background)] px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[var(--ring)]"
              rows={4}
            />
          </div>
          <div>
            <label className="block text-sm font-medium mb-1.5">Priority</label>
            <select
              value={newStory.priority}
              onChange={(e) =>
                setNewStory({ ...newStory, priority: parseInt(e.target.value) })
              }
              className="rounded-lg border border-[var(--border)] bg-[var(--background)] px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[var(--ring)]"
            >
              <option value={1}>1 - Critical</option>
              <option value={2}>2 - High</option>
              <option value={3}>3 - Medium</option>
              <option value={4}>4 - Low</option>
            </select>
          </div>
          <div className="flex gap-2">
            <button
              type="submit"
              className="rounded-lg bg-[var(--primary)] px-4 py-2 text-sm font-medium text-[var(--primary-foreground)]"
            >
              Create Story
            </button>
            <button
              type="button"
              onClick={() => setShowCreate(false)}
              className="rounded-lg border border-[var(--border)] px-4 py-2 text-sm"
            >
              Cancel
            </button>
          </div>
        </form>
      )}

      {/* Story List */}
      <div className="space-y-3">
        {stories.map((story) => (
          <div
            key={story.id}
            className="rounded-lg border border-[var(--border)] bg-[var(--card)] p-4 hover:border-[var(--primary)]/50 transition-colors"
          >
            <div className="flex items-start justify-between">
              <Link
                href={`/projects/${projectId}/stories/${story.id}`}
                className="flex-1"
              >
                <div className="flex items-center gap-2">
                  {story.story_type === "epic" && (
                    <span className="rounded bg-purple-500/20 text-purple-400 px-1.5 py-0.5 text-xs font-medium">
                      EPIC
                    </span>
                  )}
                  <h3 className={`font-semibold ${story.parent_story_id ? "ml-4" : ""}`}>{story.title}</h3>
                  <span
                    className={`rounded-full px-2 py-0.5 text-xs ${statusColors[story.status] || "bg-zinc-700"}`}
                  >
                    {story.status}
                  </span>
                  <span className="text-xs text-[var(--muted-foreground)]">
                    P{story.priority} — {priorityLabels[story.priority] || "Medium"}
                  </span>
                  {story.figma_node_id && (
                    <span className="text-xs text-[var(--muted-foreground)]">Figma</span>
                  )}
                </div>
                {story.description && (
                  <p className="mt-1.5 text-sm text-[var(--muted-foreground)] line-clamp-2">
                    {story.description}
                  </p>
                )}
              </Link>
              <button
                onClick={(e) => { e.preventDefault(); setLaunchingStory(story); }}
                className="ml-4 shrink-0 rounded-lg bg-[var(--primary)] px-3 py-1.5 text-xs font-medium text-[var(--primary-foreground)] hover:opacity-90"
              >
                Launch Agent
              </button>
            </div>
          </div>
        ))}
        {stories.length === 0 && !showCreate && (
          <div className="text-center py-16">
            <p className="text-[var(--muted-foreground)] mb-4">
              No stories yet. Create your first user story to get started.
            </p>
            <button
              onClick={() => setShowCreate(true)}
              className="rounded-lg bg-[var(--primary)] px-4 py-2 text-sm font-medium text-[var(--primary-foreground)]"
            >
              + New Story
            </button>
          </div>
        )}
      </div>

      {/* Figma Import Modal */}
      {showFigmaImport && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60">
          <div className="w-full max-w-lg rounded-xl border border-[var(--border)] bg-[var(--card)] p-6 shadow-2xl">
            <h2 className="text-lg font-bold mb-1">Import from Figma</h2>
            <p className="text-sm text-[var(--muted-foreground)] mb-4">
              Paste a Figma design URL to auto-generate an epic with stories
            </p>

            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium mb-1.5">Figma URL</label>
                <input
                  type="url"
                  value={figmaUrl}
                  onChange={(e) => setFigmaUrl(e.target.value)}
                  placeholder="https://www.figma.com/design/ABC123/My-Portal-Design"
                  className="w-full rounded-lg border border-[var(--border)] bg-[var(--background)] px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[var(--ring)]"
                />
              </div>

              <div>
                <label className="block text-sm font-medium mb-1.5">Figma Connector</label>
                {figmaConnectors.length === 0 ? (
                  <p className="text-sm text-[var(--muted-foreground)]">
                    No Figma connector found.{" "}
                    <a href="/connectors" className="text-[var(--primary)] hover:underline">
                      Add one in Connectors
                    </a>
                  </p>
                ) : (
                  <select
                    value={selectedConnector}
                    onChange={(e) => setSelectedConnector(e.target.value)}
                    className="w-full rounded-lg border border-[var(--border)] bg-[var(--background)] px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[var(--ring)]"
                  >
                    <option value="">Select connector...</option>
                    {figmaConnectors.map((c: any) => (
                      <option key={c.id} value={c.id}>
                        {c.label} {c.instance_label ? `(${c.instance_label})` : ""} — {c.status}
                      </option>
                    ))}
                  </select>
                )}
              </div>

              <div>
                <label className="block text-sm font-medium mb-1.5">Portal Type (optional)</label>
                <select
                  value={portalType}
                  onChange={(e) => setPortalType(e.target.value)}
                  className="w-full rounded-lg border border-[var(--border)] bg-[var(--background)] px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[var(--ring)]"
                >
                  <option value="">Auto-detect</option>
                  <option value="csm_b2b">CSM B2B Portal</option>
                  <option value="employee_center">Employee Center</option>
                  <option value="custom">Custom Portal</option>
                </select>
              </div>
            </div>

            {importResult && !importResult.error && (
              <div className="mt-4 rounded-lg bg-green-500/10 border border-green-500/20 p-3">
                <p className="text-sm font-medium text-green-400">
                  Imported {importResult.stories?.length || 0} stories under epic: {importResult.epic?.title}
                </p>
                <p className="text-xs text-[var(--muted-foreground)] mt-1">
                  Design: {importResult.design_summary?.file_name} ({importResult.design_summary?.page_count} pages)
                </p>
              </div>
            )}

            {importResult?.error && (
              <div className="mt-4 rounded-lg bg-red-500/10 border border-red-500/20 p-3">
                <p className="text-sm text-red-400">{importResult.error}</p>
              </div>
            )}

            <div className="flex gap-2 mt-6">
              <button
                onClick={handleFigmaImport}
                disabled={importing || !figmaUrl || !selectedConnector}
                className="flex-1 rounded-lg bg-[var(--primary)] py-2.5 text-sm font-medium text-[var(--primary-foreground)] hover:opacity-90 disabled:opacity-40"
              >
                {importing ? "Analyzing design..." : "Import Stories"}
              </button>
              <button
                onClick={() => {
                  setShowFigmaImport(false);
                  setImportResult(null);
                }}
                className="rounded-lg border border-[var(--border)] px-4 py-2.5 text-sm"
              >
                {importResult && !importResult.error ? "Done" : "Cancel"}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Agent Launcher Modal */}
      {launchingStory && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60">
          <div className="w-full max-w-md rounded-xl border border-[var(--border)] bg-[var(--card)] p-6 shadow-2xl">
            <h2 className="text-lg font-bold mb-1">Launch AI Agent</h2>
            <p className="text-sm text-[var(--muted-foreground)] mb-4">
              for &ldquo;{launchingStory.title}&rdquo;
            </p>

            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium mb-1.5">Agent</label>
                <select
                  value={launchAgent}
                  onChange={(e) => setLaunchAgent(e.target.value)}
                  className="w-full rounded-lg border border-[var(--border)] bg-[var(--background)] px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[var(--ring)]"
                >
                  <option value="">Select an agent...</option>
                  {agents.map((a: any) => (
                    <option key={a.id} value={a.id}>
                      {a.name}
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-sm font-medium mb-1.5">
                  Target ServiceNow Instance
                </label>
                <select
                  value={launchInstance}
                  onChange={(e) => setLaunchInstance(e.target.value)}
                  className="w-full rounded-lg border border-[var(--border)] bg-[var(--background)] px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[var(--ring)]"
                >
                  <option value="">Select an instance...</option>
                  {instances.map((i: any) => (
                    <option key={i.id} value={i.id}>
                      {i.name} — {i.instance_url}
                    </option>
                  ))}
                </select>
              </div>
            </div>

            <div className="flex gap-2 mt-6">
              <button
                onClick={handleLaunch}
                disabled={!launchAgent || !launchInstance}
                className="flex-1 rounded-lg bg-[var(--primary)] py-2.5 text-sm font-medium text-[var(--primary-foreground)] hover:opacity-90 disabled:opacity-40"
              >
                🚀 Launch
              </button>
              <button
                onClick={() => {
                  setLaunchingStory(null);
                  setLaunchAgent("");
                  setLaunchInstance("");
                }}
                className="rounded-lg border border-[var(--border)] px-4 py-2.5 text-sm"
              >
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
