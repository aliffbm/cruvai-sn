"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import { api } from "@/lib/api";

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

export default function StoryDetailPage() {
  const { id: projectId, storyId } = useParams<{ id: string; storyId: string }>();
  const router = useRouter();
  const [story, setStory] = useState<any>(null);
  const [childStories, setChildStories] = useState<any[]>([]);
  const [executionPlan, setExecutionPlan] = useState<any>(null);
  const [editing, setEditing] = useState(false);
  const [editData, setEditData] = useState<any>({});
  const [showAddChild, setShowAddChild] = useState(false);
  const [newChild, setNewChild] = useState({ title: "", description: "", acceptance_criteria: "", priority: 3 });
  const [message, setMessage] = useState("");
  const [attachments, setAttachments] = useState<any[]>([]);
  const [uploading, setUploading] = useState(false);
  const [agents, setAgents] = useState<any[]>([]);
  const [connectors, setConnectors] = useState<any[]>([]);
  const [showStoryLaunch, setShowStoryLaunch] = useState(false);
  const [launchAgent, setLaunchAgent] = useState("");
  const [launchConnector, setLaunchConnector] = useState("");
  const [launching, setLaunching] = useState(false);
  const [showLaunchAll, setShowLaunchAll] = useState(false);
  const [launchingStoryId, setLaunchingStoryId] = useState<string | null>(null);

  useEffect(() => {
    if (!projectId || !storyId) return;
    loadStory();
    loadChildren();
    loadAttachments();
  }, [projectId, storyId]);

  async function loadAttachments() {
    try {
      const atts = await api.listAttachments(projectId, storyId);
      setAttachments(atts);
    } catch {}
  }

  async function handleFileUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const files = e.target.files;
    if (!files || files.length === 0) return;
    setUploading(true);
    for (const file of Array.from(files)) {
      try {
        await api.uploadAttachment(projectId, storyId, file);
      } catch (err: any) {
        setMessage(`Error uploading ${file.name}: ${err.message}`);
      }
    }
    await loadAttachments();
    setUploading(false);
    e.target.value = "";
  }

  async function handleDeleteAttachment(attachmentId: string) {
    try {
      await api.deleteAttachment(projectId, storyId, attachmentId);
      setAttachments((prev) => prev.filter((a) => a.id !== attachmentId));
    } catch (err: any) {
      setMessage(`Error: ${err.message}`);
    }
  }

  async function loadStory() {
    const token = api.getToken();
    const res = await fetch(`/api/v1/projects/${projectId}/stories/${storyId}`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    if (res.ok) {
      const data = await res.json();
      setStory(data);
      setEditData(data);
    }
  }

  async function loadChildren() {
    try {
      const plan = await api.getEpicExecutionPlan(projectId, storyId);
      setExecutionPlan(plan);
      setChildStories(plan.stories || []);
    } catch {
      // Fallback: load all stories and filter
      const allStories = await api.listStories(projectId);
      setChildStories(allStories.filter((s: any) => s.parent_story_id === storyId));
    }
  }

  async function loadAgentsAndConnectors() {
    const token = api.getToken();
    try {
      const agentsRes = await fetch("/api/v1/agents", { headers: { Authorization: `Bearer ${token}` } });
      if (agentsRes.ok) {
        const all = await agentsRes.json();
        // Hide specialists from the primary-agent launch dropdown — they are
        // delegation-only targets, not story-owning runners.
        setAgents(all.filter((a: any) => a.agent_type !== "specialist" && a.is_active !== false));
      }
    } catch {}
    try {
      const conns = await api.listConnectors();
      setConnectors(conns.filter((c: any) => c.platform === "servicenow" && c.status === "connected"));
    } catch {}
  }

  async function handleSave() {
    const token = api.getToken();
    const res = await fetch(`/api/v1/projects/${projectId}/stories/${storyId}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
      body: JSON.stringify({
        title: editData.title,
        description: editData.description,
        acceptance_criteria: editData.acceptance_criteria,
        priority: editData.priority,
        status: editData.status,
        figma_file_url: editData.figma_file_url ?? null,
        figma_node_id: editData.figma_node_id ?? null,
      }),
    });
    if (res.ok) {
      setStory(await res.json());
      setEditing(false);
      setMessage("Story updated");
      setTimeout(() => setMessage(""), 3000);
    }
  }

  async function handleFigmaPreview() {
    setMessage("Fetching Figma preview…");
    const token = api.getToken();
    const res = await fetch(
      `/api/v1/projects/${projectId}/stories/${storyId}/figma-preview`,
      { headers: { Authorization: `Bearer ${token}` } },
    );
    if (res.ok) {
      const preview = await res.json();
      setMessage(
        `Figma file: ${preview.name || preview.file_key || "(unknown)"} \u2014 last modified ${preview.last_modified || "?"}`,
      );
    } else {
      const err = await res.json().catch(() => ({}));
      setMessage(`Figma preview failed: ${err.detail || res.status}`);
    }
    setTimeout(() => setMessage(""), 6000);
  }

  async function handleCreateChild(e: React.FormEvent) {
    e.preventDefault();
    const token = api.getToken();
    const res = await fetch(`/api/v1/projects/${projectId}/stories`, {
      method: "POST",
      headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
      body: JSON.stringify({
        ...newChild,
        parent_story_id: storyId,
        story_type: "story",
      }),
    });
    if (res.ok) {
      setShowAddChild(false);
      setNewChild({ title: "", description: "", acceptance_criteria: "", priority: 3 });
      loadChildren();
      setMessage("Child story created");
      setTimeout(() => setMessage(""), 3000);
    }
  }

  if (!story) return <div className="text-[var(--muted-foreground)]">Loading...</div>;

  const isEpic = story.story_type === "epic";

  return (
    <div className="max-w-4xl">
      {/* Breadcrumb */}
      <div className="flex items-center gap-2 text-xs text-[var(--muted-foreground)] mb-4">
        <Link href={`/projects/${projectId}`} className="hover:text-[var(--foreground)]">Project</Link>
        <span>/</span>
        <Link href={`/projects/${projectId}/stories`} className="hover:text-[var(--foreground)]">Stories</Link>
        <span>/</span>
        <span className="text-[var(--foreground)]">{story.title}</span>
      </div>

      {/* Header */}
      <div className="flex items-start justify-between mb-6">
        <div>
          <div className="flex items-center gap-2">
            {isEpic && (
              <span className="rounded bg-purple-500/20 text-purple-400 px-2 py-0.5 text-xs font-medium">EPIC</span>
            )}
            {!editing ? (
              <h1 className="text-2xl font-bold">{story.title}</h1>
            ) : (
              <input
                value={editData.title}
                onChange={(e) => setEditData({ ...editData, title: e.target.value })}
                className="text-2xl font-bold bg-transparent border-b border-[var(--border)] focus:outline-none focus:border-[var(--primary)] w-full"
              />
            )}
          </div>
          <div className="flex items-center gap-2 mt-2">
            <span className={`rounded-full px-2 py-0.5 text-xs ${statusColors[story.status] || "bg-zinc-700"}`}>
              {story.status}
            </span>
            <span className="text-xs text-[var(--muted-foreground)]">
              P{story.priority} — {priorityLabels[story.priority] || "Medium"}
            </span>
            {story.figma_node_id && (
              <span className="text-xs text-[var(--muted-foreground)]">Figma node: {story.figma_node_id}</span>
            )}
            {story.figma_file_url && (
              <a
                href={story.figma_file_url}
                target="_blank"
                rel="noopener noreferrer"
                className="text-xs text-[var(--primary)] underline"
              >
                Open Figma design
              </a>
            )}
            {story.figma_file_url && (
              <button
                onClick={handleFigmaPreview}
                className="text-xs rounded-md border border-[var(--border)] px-2 py-0.5 hover:bg-[var(--card)]"
              >
                Preview
              </button>
            )}
          </div>
        </div>
        <div className="flex gap-2">
          {!editing ? (
            <button onClick={() => setEditing(true)} className="rounded-lg border border-[var(--border)] px-3 py-1.5 text-xs hover:bg-[var(--secondary)]">
              Edit
            </button>
          ) : (
            <>
              <button onClick={handleSave} className="rounded-lg bg-[var(--primary)] px-3 py-1.5 text-xs text-[var(--primary-foreground)]">Save</button>
              <button onClick={() => { setEditing(false); setEditData(story); }} className="rounded-lg border border-[var(--border)] px-3 py-1.5 text-xs">Cancel</button>
            </>
          )}
        </div>
      </div>

      {message && (
        <div className="mb-4 rounded-lg bg-green-500/10 text-green-400 p-3 text-sm">{message}</div>
      )}

      {/* Status & Priority (editable) */}
      {editing && (
        <div className="mb-6 flex gap-4">
          <div>
            <label className="text-xs font-medium text-[var(--muted-foreground)]">Status</label>
            <select
              value={editData.status}
              onChange={(e) => setEditData({ ...editData, status: e.target.value })}
              className="mt-1 block rounded-lg border border-[var(--border)] bg-[var(--background)] px-3 py-2 text-sm"
            >
              {["backlog", "ready", "in_progress", "review", "testing", "done"].map((s) => (
                <option key={s} value={s}>{s}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="text-xs font-medium text-[var(--muted-foreground)]">Priority</label>
            <select
              value={editData.priority}
              onChange={(e) => setEditData({ ...editData, priority: parseInt(e.target.value) })}
              className="mt-1 block rounded-lg border border-[var(--border)] bg-[var(--background)] px-3 py-2 text-sm"
            >
              <option value={1}>1 - Critical</option>
              <option value={2}>2 - High</option>
              <option value={3}>3 - Medium</option>
              <option value={4}>4 - Low</option>
            </select>
          </div>
        </div>
      )}

      {/* Description */}
      <div className="mb-6 rounded-lg border border-[var(--border)] bg-[var(--card)] p-4">
        <h2 className="text-sm font-bold mb-2">Description</h2>
        {editing ? (
          <textarea
            value={editData.description || ""}
            onChange={(e) => setEditData({ ...editData, description: e.target.value })}
            rows={5}
            className="w-full rounded-lg border border-[var(--border)] bg-[var(--background)] px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[var(--ring)]"
          />
        ) : (
          <p className="text-sm text-[var(--muted-foreground)] whitespace-pre-line">
            {story.description || "No description"}
          </p>
        )}
      </div>

      {/* Acceptance Criteria */}
      <div className="mb-6 rounded-lg border border-[var(--border)] bg-[var(--card)] p-4">
        <h2 className="text-sm font-bold mb-2">Acceptance Criteria</h2>
        {editing ? (
          <textarea
            value={editData.acceptance_criteria || ""}
            onChange={(e) => setEditData({ ...editData, acceptance_criteria: e.target.value })}
            rows={5}
            placeholder="- [ ] Criteria 1&#10;- [ ] Criteria 2"
            className="w-full rounded-lg border border-[var(--border)] bg-[var(--background)] px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[var(--ring)]"
          />
        ) : (
          <div className="text-sm text-[var(--muted-foreground)] whitespace-pre-line">
            {story.acceptance_criteria || "No acceptance criteria defined"}
          </div>
        )}
      </div>

      {/* Figma link */}
      <div className="mb-6 rounded-lg border border-[var(--border)] bg-[var(--card)] p-4">
        <h2 className="text-sm font-bold mb-2">Figma design</h2>
        {editing ? (
          <>
            <input
              value={editData.figma_file_url || ""}
              onChange={(e) => setEditData({ ...editData, figma_file_url: e.target.value })}
              placeholder="https://figma.com/design/FILE_KEY/..."
              className="w-full rounded-lg border border-[var(--border)] bg-[var(--background)] px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[var(--ring)]"
            />
            <p className="mt-1 text-xs text-[var(--muted-foreground)]">
              The Portal agent will fetch this design during planning if the project has a
              Figma connector configured.
            </p>
            <input
              value={editData.figma_node_id || ""}
              onChange={(e) => setEditData({ ...editData, figma_node_id: e.target.value })}
              placeholder="Optional: specific node id"
              className="mt-2 w-full rounded-lg border border-[var(--border)] bg-[var(--background)] px-3 py-2 text-xs focus:outline-none focus:ring-2 focus:ring-[var(--ring)]"
            />
          </>
        ) : story.figma_file_url ? (
          <div className="flex items-center gap-2">
            <a
              href={story.figma_file_url}
              target="_blank"
              rel="noopener noreferrer"
              className="text-sm text-[var(--primary)] underline break-all"
            >
              {story.figma_file_url}
            </a>
            <button
              onClick={handleFigmaPreview}
              className="text-xs rounded-md border border-[var(--border)] px-2 py-1 hover:bg-[var(--secondary)]"
            >
              Preview via connector
            </button>
          </div>
        ) : (
          <p className="text-sm text-[var(--muted-foreground)]">
            No Figma design linked. Click Edit to paste the Figma file URL.
          </p>
        )}
      </div>

      {/* AI Agent Analyzer */}
      <StoryAnalysisPanel
        projectId={projectId}
        storyId={storyId}
        isEpic={isEpic}
      />

      {/* Audit Activity */}
      <StoryActivityPanel
        projectId={projectId}
        storyId={storyId}
      />

      {/* Figma image capture */}
      {story.figma_file_url && !isEpic && (
        <FigmaImageCapturePanel
          projectId={projectId}
          storyId={storyId}
        />
      )}

      {/* Attachments */}
      <div className="mb-6 rounded-lg border border-[var(--border)] bg-[var(--card)] p-4">
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-sm font-bold">
            Attachments
            {attachments.length > 0 && (
              <span className="ml-1.5 rounded-full bg-[var(--secondary)] px-1.5 py-0.5 text-xs">
                {attachments.length}
              </span>
            )}
          </h2>
          <label className="rounded-lg bg-[var(--primary)] px-3 py-1.5 text-xs font-medium text-[var(--primary-foreground)] cursor-pointer hover:opacity-90">
            {uploading ? "Uploading..." : "Upload Image"}
            <input
              type="file"
              accept="image/*,.pdf"
              multiple
              onChange={handleFileUpload}
              className="hidden"
              disabled={uploading}
            />
          </label>
        </div>

        {attachments.length > 0 ? (
          <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
            {attachments.map((att) => (
              <div key={att.id} className="relative group rounded-lg border border-[var(--border)] overflow-hidden">
                {att.mime_type.startsWith("image/") ? (
                  <img
                    src={att.url}
                    alt={att.caption || att.filename}
                    className="w-full h-40 object-cover"
                  />
                ) : (
                  <div className="w-full h-40 flex items-center justify-center bg-[var(--secondary)]">
                    <span className="text-xs text-[var(--muted-foreground)]">{att.filename}</span>
                  </div>
                )}
                <div className="p-2">
                  <p className="text-xs text-[var(--muted-foreground)] truncate">{att.filename}</p>
                  <p className="text-xs text-[var(--muted-foreground)]">{(att.file_size / 1024).toFixed(0)} KB</p>
                </div>
                <button
                  onClick={() => handleDeleteAttachment(att.id)}
                  className="absolute top-1 right-1 opacity-0 group-hover:opacity-100 rounded bg-red-500/80 px-1.5 py-0.5 text-xs text-white transition-opacity"
                >
                  X
                </button>
              </div>
            ))}
          </div>
        ) : (
          <p className="text-sm text-[var(--muted-foreground)]">
            No attachments. Upload mockups or screenshots for the agent to reference.
          </p>
        )}
      </div>

      {/* Launch Agent (for non-epic stories) */}
      {!isEpic && (
        <div className="mb-6">
          <button
            onClick={() => { setShowStoryLaunch(true); loadAgentsAndConnectors(); }}
            className="rounded-lg bg-[var(--primary)] px-5 py-2.5 text-sm font-medium text-[var(--primary-foreground)]"
          >
            Launch Agent
          </button>
        </div>
      )}

      {/* Story Launch Modal */}
      {showStoryLaunch && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60">
          <div className="w-full max-w-md rounded-xl border border-[var(--border)] bg-[var(--card)] p-6 shadow-2xl">
            <h2 className="text-lg font-bold mb-1">Launch Agent</h2>
            <p className="text-sm text-[var(--muted-foreground)] mb-4">
              for &ldquo;{story?.title}&rdquo;
            </p>
            <div className="space-y-3">
              <div>
                <label className="block text-sm font-medium mb-1">Agent</label>
                <select
                  value={launchAgent}
                  onChange={(e) => setLaunchAgent(e.target.value)}
                  className="w-full rounded-lg border border-[var(--border)] bg-[var(--background)] px-3 py-2 text-sm"
                >
                  <option value="">Select agent...</option>
                  {agents.map((a: any) => (
                    <option key={a.id} value={a.id}>{a.name}</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium mb-1">ServiceNow Instance</label>
                <select
                  value={launchConnector}
                  onChange={(e) => setLaunchConnector(e.target.value)}
                  className="w-full rounded-lg border border-[var(--border)] bg-[var(--background)] px-3 py-2 text-sm"
                >
                  <option value="">Select instance...</option>
                  {connectors.map((c: any) => (
                    <option key={c.id} value={c.id}>{c.label} {c.instance_label ? `(${c.instance_label})` : ""}</option>
                  ))}
                </select>
              </div>
            </div>
            <div className="flex gap-2 mt-5">
              <button
                onClick={async () => {
                  if (!launchAgent || !launchConnector) return;
                  setLaunching(true);
                  try {
                    const job = await api.createJob(projectId, {
                      agent_id: launchAgent,
                      story_id: storyId,
                      instance_id: launchConnector,
                    });
                    window.location.href = `/projects/${projectId}/jobs/${job.id}`;
                  } catch (e: any) {
                    setMessage(`Error: ${e.message}`);
                    setLaunching(false);
                  }
                }}
                disabled={launching || !launchAgent || !launchConnector}
                className="flex-1 rounded-lg bg-[var(--primary)] py-2.5 text-sm font-medium text-[var(--primary-foreground)] disabled:opacity-40"
              >
                {launching ? "Launching..." : "Launch"}
              </button>
              <button
                onClick={() => setShowStoryLaunch(false)}
                className="rounded-lg border border-[var(--border)] px-4 py-2.5 text-sm"
              >
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Execution Plan (for epics) or Parent link (for stories) */}
      {isEpic && (
        <div className="mb-6">
          {/* Progress bar */}
          {executionPlan && (
            <div className="mb-4 rounded-lg border border-[var(--border)] bg-[var(--card)] p-4">
              <div className="flex items-center justify-between mb-2">
                <h2 className="text-sm font-bold">Execution Plan</h2>
                <span className="text-xs text-[var(--muted-foreground)]">
                  {executionPlan.completed}/{executionPlan.total} completed
                </span>
              </div>
              <div className="h-2 rounded-full bg-[var(--secondary)]">
                <div
                  className="h-full rounded-full bg-[var(--primary)] transition-all"
                  style={{ width: `${executionPlan.total > 0 ? (executionPlan.completed / executionPlan.total) * 100 : 0}%` }}
                />
              </div>
            </div>
          )}

          {/* Launch All button */}
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-sm font-bold">
              Stories
              <span className="ml-1.5 rounded-full bg-[var(--secondary)] px-1.5 py-0.5 text-xs">
                {childStories.length}
              </span>
            </h2>
            <div className="flex gap-2">
              <button
                onClick={() => setShowAddChild(!showAddChild)}
                className="rounded-lg border border-[var(--border)] px-3 py-1.5 text-xs hover:bg-[var(--secondary)]"
              >
                + Add Story
              </button>
              <button
                onClick={() => { setShowLaunchAll(true); loadAgentsAndConnectors(); }}
                className="rounded-lg bg-[var(--primary)] px-4 py-1.5 text-xs font-medium text-[var(--primary-foreground)]"
              >
                Launch Agent for Epic
              </button>
            </div>
          </div>

          {showAddChild && (
            <form onSubmit={handleCreateChild} className="mb-4 rounded-lg border border-[var(--border)] bg-[var(--card)] p-4 space-y-3">
              <input
                type="text"
                value={newChild.title}
                onChange={(e) => setNewChild({ ...newChild, title: e.target.value })}
                placeholder="Story title"
                className="w-full rounded-lg border border-[var(--border)] bg-[var(--background)] px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[var(--ring)]"
                required
              />
              <textarea
                value={newChild.description}
                onChange={(e) => setNewChild({ ...newChild, description: e.target.value })}
                placeholder="Description"
                rows={2}
                className="w-full rounded-lg border border-[var(--border)] bg-[var(--background)] px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[var(--ring)]"
              />
              <textarea
                value={newChild.acceptance_criteria}
                onChange={(e) => setNewChild({ ...newChild, acceptance_criteria: e.target.value })}
                placeholder="Acceptance criteria"
                rows={3}
                className="w-full rounded-lg border border-[var(--border)] bg-[var(--background)] px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[var(--ring)]"
              />
              <div className="flex gap-2">
                <button type="submit" className="rounded-lg bg-[var(--primary)] px-3 py-1.5 text-xs text-[var(--primary-foreground)]">Create</button>
                <button type="button" onClick={() => setShowAddChild(false)} className="rounded-lg border border-[var(--border)] px-3 py-1.5 text-xs">Cancel</button>
              </div>
            </form>
          )}

          {/* Ordered story list */}
          <div className="space-y-2">
            {childStories.map((child, idx) => (
              <div
                key={child.id}
                className="rounded-lg border border-[var(--border)] bg-[var(--card)] p-3 hover:border-[var(--primary)]/50 transition-colors"
              >
                <div className="flex items-center justify-between">
                  <Link
                    href={`/projects/${projectId}/stories/${child.id}`}
                    className="flex items-center gap-3 flex-1"
                  >
                    <span className={`flex h-6 w-6 shrink-0 items-center justify-center rounded-full text-xs font-bold ${
                      child.status === "done"
                        ? "bg-green-500/20 text-green-400"
                        : child.status === "in_progress"
                        ? "bg-yellow-500/20 text-yellow-400"
                        : "bg-[var(--secondary)] text-[var(--muted-foreground)]"
                    }`}>
                      {child.status === "done" ? "✓" : child.execution_step || idx + 1}
                    </span>
                    <div>
                      <h3 className="text-sm font-medium">{child.title}</h3>
                      {child.description && (
                        <p className="text-xs text-[var(--muted-foreground)] line-clamp-1 mt-0.5">{child.description}</p>
                      )}
                    </div>
                  </Link>
                  <div className="flex items-center gap-2 ml-3 shrink-0">
                    <span className={`rounded-full px-2 py-0.5 text-xs ${statusColors[child.status] || "bg-zinc-700"}`}>
                      {child.status}
                    </span>
                    <span className="text-xs text-[var(--muted-foreground)]">P{child.priority}</span>
                    {child.status !== "done" && (
                      <button
                        onClick={(e) => {
                          e.preventDefault();
                          setShowLaunchAll(true);
                          loadAgentsAndConnectors();
                          // Pre-select this specific story for launch
                          setLaunchingStoryId(child.id);
                        }}
                        className="rounded bg-[var(--primary)] px-2.5 py-1 text-xs font-medium text-[var(--primary-foreground)] hover:opacity-90"
                      >
                        Launch
                      </button>
                    )}
                  </div>
                </div>
              </div>
            ))}
            {childStories.length === 0 && (
              <p className="text-sm text-[var(--muted-foreground)]">No child stories yet.</p>
            )}
          </div>

          {/* Launch All Modal */}
          {showLaunchAll && (
            <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60">
              <div className="w-full max-w-lg rounded-xl border border-[var(--border)] bg-[var(--card)] p-6 shadow-2xl">
                <h2 className="text-lg font-bold mb-1">Launch Agent for Epic</h2>
                <p className="text-sm text-[var(--muted-foreground)] mb-2">
                  The agent will execute stories in the recommended order:
                </p>
                <ol className="mb-4 space-y-1 text-xs text-[var(--muted-foreground)]">
                  {childStories.map((c, i) => (
                    <li key={c.id} className="flex items-center gap-2">
                      <span className="font-mono w-5 text-right">{i + 1}.</span>
                      <span className={c.status === "done" ? "line-through opacity-50" : ""}>{c.title}</span>
                      {c.status === "done" && <span className="text-green-400">✓</span>}
                    </li>
                  ))}
                </ol>

                <div className="space-y-3">
                  <div>
                    <label className="block text-sm font-medium mb-1">Agent</label>
                    <select
                      value={launchAgent}
                      onChange={(e) => setLaunchAgent(e.target.value)}
                      className="w-full rounded-lg border border-[var(--border)] bg-[var(--background)] px-3 py-2 text-sm"
                    >
                      <option value="">Select agent...</option>
                      {agents.map((a: any) => (
                        <option key={a.id} value={a.id}>{a.name}</option>
                      ))}
                    </select>
                  </div>
                  <div>
                    <label className="block text-sm font-medium mb-1">ServiceNow Instance</label>
                    <select
                      value={launchConnector}
                      onChange={(e) => setLaunchConnector(e.target.value)}
                      className="w-full rounded-lg border border-[var(--border)] bg-[var(--background)] px-3 py-2 text-sm"
                    >
                      <option value="">Select instance...</option>
                      {connectors.map((c: any) => (
                        <option key={c.id} value={c.id}>{c.label} {c.instance_label ? `(${c.instance_label})` : ""}</option>
                      ))}
                    </select>
                  </div>
                </div>

                {message && (
                  <div className={`mt-3 rounded p-2 text-xs ${message.startsWith("Error") ? "bg-red-500/10 text-red-400" : "bg-green-500/10 text-green-400"}`}>
                    {message}
                  </div>
                )}

                <div className="flex gap-2 mt-5">
                  <button
                    onClick={async () => {
                      if (!launchAgent || !launchConnector) return;
                      setLaunching(true);
                      setMessage("");
                      try {
                        // Launch first non-done story
                        const nextStory = childStories.find((c) => c.status !== "done");
                        if (!nextStory) {
                          setMessage("All stories are already done!");
                          setLaunching(false);
                          return;
                        }
                        const job = await api.createJob(projectId, {
                          agent_id: launchAgent,
                          story_id: nextStory.id,
                          instance_id: launchConnector,
                        });
                        window.location.href = `/projects/${projectId}/jobs/${job.id}`;
                      } catch (e: any) {
                        setMessage(`Error: ${e.message}`);
                      }
                      setLaunching(false);
                    }}
                    disabled={launching || !launchAgent || !launchConnector}
                    className="flex-1 rounded-lg bg-[var(--primary)] py-2.5 text-sm font-medium text-[var(--primary-foreground)] disabled:opacity-40"
                  >
                    {launching ? "Launching..." : "Launch Next Story"}
                  </button>
                  <button
                    onClick={() => { setShowLaunchAll(false); setMessage(""); }}
                    className="rounded-lg border border-[var(--border)] px-4 py-2.5 text-sm"
                  >
                    Cancel
                  </button>
                </div>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Parent Epic link */}
      {story.parent_story_id && (
        <div className="mb-6">
          <Link
            href={`/projects/${projectId}/stories/${story.parent_story_id}`}
            className="text-xs text-[var(--primary)] hover:underline"
          >
            ← Back to parent epic
          </Link>
        </div>
      )}

      {/* Actions */}
      <div className="flex gap-3">
        <button
          onClick={() => router.push(`/projects/${projectId}/stories`)}
          className="rounded-lg border border-[var(--border)] px-4 py-2 text-sm hover:bg-[var(--secondary)]"
        >
          Back to Stories
        </button>
      </div>
    </div>
  );
}


// ---------------------------------------------------------------------------
// AI Agent Analyzer panel — renders latest StoryAnalysis with attribution
// ---------------------------------------------------------------------------

function StoryAnalysisPanel({
  projectId,
  storyId,
  isEpic,
}: {
  projectId: string;
  storyId: string;
  isEpic: boolean;
}) {
  const [analysis, setAnalysis] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [dispatching, setDispatching] = useState(false);
  const [approving, setApproving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = async () => {
    setLoading(true);
    setError(null);
    try {
      const token = api.getToken();
      const res = await fetch(
        `/api/v1/projects/${projectId}/stories/${storyId}/analyses/latest`,
        { headers: { Authorization: `Bearer ${token}` } },
      );
      if (res.ok) {
        const data = await res.json();
        setAnalysis(data?.analysis ?? null);
      } else {
        setAnalysis(null);
      }
    } catch (e: any) {
      setError(String(e?.message || e));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, [projectId, storyId]);

  const runAnalyzer = async () => {
    setDispatching(true);
    setError(null);
    try {
      const token = api.getToken();
      const res = await fetch(
        `/api/v1/projects/${projectId}/stories/${storyId}/analyze`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
          body: JSON.stringify({}),
        },
      );
      if (!res.ok) throw new Error(await res.text());
      const { job_id } = await res.json();
      window.location.href = `/projects/${projectId}/jobs/${job_id}`;
    } catch (e: any) {
      setError(String(e?.message || e));
      setDispatching(false);
    }
  };

  const approve = async () => {
    if (!analysis?.id) return;
    setApproving(true);
    setError(null);
    try {
      const token = api.getToken();
      const res = await fetch(
        `/api/v1/projects/${projectId}/stories/${storyId}/analyses/${analysis.id}/approve`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        },
      );
      if (!res.ok) throw new Error(await res.text());
      await load();
    } catch (e: any) {
      setError(String(e?.message || e));
    } finally {
      setApproving(false);
    }
  };

  const statusBadgeClass: Record<string, string> = {
    draft: "bg-amber-500/20 text-amber-400",
    approved: "bg-green-500/20 text-green-400",
    outdated: "bg-zinc-700 text-zinc-400",
    superseded: "bg-zinc-700 text-zinc-400",
  };

  return (
    <div className="mb-6 rounded-lg border border-[var(--border)] bg-[var(--card)] p-4">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <h2 className="text-sm font-bold">AI Agent Analyzer</h2>
          {analysis && (
            <span
              className={`rounded-full px-2 py-0.5 text-xs ${statusBadgeClass[analysis.status] || "bg-zinc-700"}`}
            >
              {analysis.status}
            </span>
          )}
          {analysis && (
            <span className="text-xs text-[var(--muted-foreground)]">
              v{analysis.version_number}
            </span>
          )}
        </div>
        <div className="flex gap-2">
          {analysis?.status === "draft" && (
            <button
              onClick={approve}
              disabled={approving}
              className="rounded-md bg-green-500/20 text-green-400 px-3 py-1 text-xs hover:bg-green-500/30 disabled:opacity-40"
            >
              {approving ? "Approving..." : "Approve"}
            </button>
          )}
          <button
            onClick={runAnalyzer}
            disabled={dispatching || isEpic}
            title={isEpic ? "Run the analyzer on individual child stories" : ""}
            className="rounded-md bg-[var(--primary)] px-3 py-1 text-xs font-medium text-[var(--primary-foreground)] disabled:opacity-40"
          >
            {dispatching ? "Dispatching..." : analysis ? "Re-analyze" : "Run Analyzer"}
          </button>
        </div>
      </div>

      {error && (
        <div className="mb-2 rounded border border-red-500/30 bg-red-500/10 p-2 text-xs text-red-400">
          {error}
        </div>
      )}

      {loading && <p className="text-xs text-[var(--muted-foreground)]">Loading analysis...</p>}

      {!loading && !analysis && (
        <p className="text-sm text-[var(--muted-foreground)]">
          No analysis yet. The AI Agent Analyzer will review this story, consult
          the toolkit specialists, survey the target ServiceNow instance for
          reusable OOB artifacts, and produce a reviewable technical design.
        </p>
      )}

      {analysis && (
        <div className="space-y-3">
          <div className="text-xs text-[var(--muted-foreground)]">
            Analysis by <span className="text-[var(--foreground)] font-medium">AI Agent Analyzer</span>
            {analysis.authored_by_model && (
              <> · <span className="font-mono">{analysis.authored_by_model}</span></>
            )}
            {" · "}
            {new Date(analysis.created_at).toLocaleString()}
            {analysis.authored_by_job_id && (
              <> · <a href={`/projects/${projectId}/jobs/${analysis.authored_by_job_id}`} className="underline">view job</a></>
            )}
          </div>

          {analysis.summary && (
            <div>
              <h3 className="text-xs font-bold uppercase text-[var(--muted-foreground)] mb-1">Summary</h3>
              <p className="text-sm">{analysis.summary}</p>
            </div>
          )}

          {analysis.design_rationale && (
            <div>
              <h3 className="text-xs font-bold uppercase text-[var(--muted-foreground)] mb-1">Design rationale</h3>
              <p className="text-sm whitespace-pre-line">{analysis.design_rationale}</p>
            </div>
          )}

          {analysis.proposed_artifacts?.length > 0 && (
            <div>
              <h3 className="text-xs font-bold uppercase text-[var(--muted-foreground)] mb-1">
                Proposed artifacts ({analysis.proposed_artifacts.length})
              </h3>
              <div className="space-y-1">
                {analysis.proposed_artifacts.map((a: any, i: number) => (
                  <div key={i} className="rounded border border-[var(--border)] p-2 text-xs">
                    <div className="flex items-center gap-2">
                      <span className={`rounded px-1.5 py-0.5 text-xs ${
                        a.action === "create" ? "bg-green-500/20 text-green-400"
                          : a.action === "update" ? "bg-blue-500/20 text-blue-400"
                          : a.action === "delete" ? "bg-red-500/20 text-red-400"
                          : "bg-zinc-700"
                      }`}>{a.action}</span>
                      <span className="font-mono text-[var(--muted-foreground)]">{a.sn_table}</span>
                      <span className="font-medium">{a.name}</span>
                      {a.oob_reused && <span className="text-xs text-green-400">· OOB reuse</span>}
                    </div>
                    {a.rationale && (
                      <p className="mt-1 text-[var(--muted-foreground)]">{a.rationale}</p>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}

          {analysis.acceptance_criteria_mapping?.length > 0 && (
            <div>
              <h3 className="text-xs font-bold uppercase text-[var(--muted-foreground)] mb-1">
                Acceptance criteria coverage
              </h3>
              <div className="space-y-1">
                {analysis.acceptance_criteria_mapping.map((ac: any, i: number) => (
                  <div key={i} className="flex items-start gap-2 text-xs">
                    <span className={ac.covered ? "text-green-400" : "text-red-400"}>
                      {ac.covered ? "✓" : "✗"}
                    </span>
                    <div className="flex-1">
                      <p>{ac.criterion}</p>
                      {ac.proposed_coverage && (
                        <p className="text-[var(--muted-foreground)]">→ {ac.proposed_coverage}</p>
                      )}
                      {ac.gap_reason && (
                        <p className="text-amber-400">gap: {ac.gap_reason}</p>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {analysis.oob_reuse?.length > 0 && (
            <div>
              <h3 className="text-xs font-bold uppercase text-[var(--muted-foreground)] mb-1">
                OOB reuse candidates ({analysis.oob_reuse.length})
              </h3>
              <ul className="space-y-0.5 text-xs">
                {analysis.oob_reuse.map((o: any, i: number) => (
                  <li key={i}>
                    <span className="font-mono text-[var(--muted-foreground)]">{o.sn_table}</span>
                    {" · "}
                    <span className="font-medium">{o.name}</span>
                    {o.reuse_mode && <span className="text-[var(--muted-foreground)]"> · {o.reuse_mode}</span>}
                    {o.why && <span className="text-[var(--muted-foreground)]"> — {o.why}</span>}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {analysis.specialist_consults?.length > 0 && (
            <div>
              <h3 className="text-xs font-bold uppercase text-[var(--muted-foreground)] mb-1">Recommended specialist consults</h3>
              <ul className="space-y-0.5 text-xs">
                {analysis.specialist_consults.map((s: any, i: number) => (
                  <li key={i}><span className="font-mono">{s.slug}</span> — {s.reason}</li>
                ))}
              </ul>
            </div>
          )}

          {analysis.risks?.length > 0 && (
            <div>
              <h3 className="text-xs font-bold uppercase text-amber-400 mb-1">Risks</h3>
              <ul className="list-disc pl-4 space-y-0.5 text-xs text-amber-400">
                {analysis.risks.map((r: string, i: number) => <li key={i}>{r}</li>)}
              </ul>
            </div>
          )}
        </div>
      )}
    </div>
  );
}


// ---------------------------------------------------------------------------
// Activity (StoryNote) panel — append-only audit timeline
// ---------------------------------------------------------------------------

function StoryActivityPanel({
  projectId,
  storyId,
}: {
  projectId: string;
  storyId: string;
}) {
  const [notes, setNotes] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [draft, setDraft] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const load = async () => {
    setLoading(true);
    try {
      const token = api.getToken();
      const res = await fetch(
        `/api/v1/projects/${projectId}/stories/${storyId}/notes`,
        { headers: { Authorization: `Bearer ${token}` } },
      );
      if (res.ok) setNotes(await res.json());
    } finally {
      setLoading(false);
    }
  };
  useEffect(() => { load(); }, [projectId, storyId]);

  const submit = async () => {
    if (!draft.trim()) return;
    setSubmitting(true);
    try {
      const token = api.getToken();
      await fetch(
        `/api/v1/projects/${projectId}/stories/${storyId}/notes`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
          body: JSON.stringify({ content: draft }),
        },
      );
      setDraft("");
      await load();
    } finally {
      setSubmitting(false);
    }
  };

  const typeBadge: Record<string, string> = {
    requirement_change: "bg-blue-500/20 text-blue-400",
    analysis_update: "bg-purple-500/20 text-purple-400",
    approval: "bg-green-500/20 text-green-400",
    build_outcome: "bg-orange-500/20 text-orange-400",
    ac_verification: "bg-pink-500/20 text-pink-400",
    manual: "bg-zinc-700 text-zinc-300",
  };

  return (
    <div className="mb-6 rounded-lg border border-[var(--border)] bg-[var(--card)] p-4">
      <h2 className="text-sm font-bold mb-3">Activity</h2>

      <div className="mb-3 flex gap-2">
        <input
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          placeholder="Add a note to the audit trail..."
          className="flex-1 rounded-md border border-[var(--border)] bg-[var(--background)] px-2 py-1 text-sm focus:outline-none focus:ring-2 focus:ring-[var(--ring)]"
        />
        <button
          onClick={submit}
          disabled={submitting || !draft.trim()}
          className="rounded-md bg-[var(--primary)] px-3 py-1 text-xs text-[var(--primary-foreground)] disabled:opacity-40"
        >
          {submitting ? "..." : "Add"}
        </button>
      </div>

      {loading && <p className="text-xs text-[var(--muted-foreground)]">Loading activity...</p>}

      {!loading && notes.length === 0 && (
        <p className="text-xs text-[var(--muted-foreground)]">
          No activity yet. Requirement changes, analysis updates, and build
          outcomes are automatically logged here.
        </p>
      )}

      <div className="space-y-2">
        {notes.map((n) => (
          <div key={n.id} className="rounded border border-[var(--border)] p-2 text-xs">
            <div className="flex items-center gap-2 mb-1">
              <span className={`rounded-full px-2 py-0.5 ${typeBadge[n.note_type] || "bg-zinc-700"}`}>
                {n.note_type}
              </span>
              <span className="text-[var(--muted-foreground)]">{new Date(n.created_at).toLocaleString()}</span>
              {n.author_agent_slug && (
                <span className="text-[var(--muted-foreground)]">· agent: {n.author_agent_slug}</span>
              )}
            </div>
            <p>{n.content}</p>
            {n.diff && (
              <pre className="mt-1 rounded bg-black/40 p-2 overflow-x-auto">
                {JSON.stringify(n.diff, null, 2)}
              </pre>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}


// ---------------------------------------------------------------------------
// Figma image capture panel
// ---------------------------------------------------------------------------

function FigmaImageCapturePanel({
  projectId,
  storyId,
}: {
  projectId: string;
  storyId: string;
}) {
  const [capturing, setCapturing] = useState(false);
  const [result, setResult] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);

  const capture = async () => {
    setCapturing(true);
    setError(null);
    try {
      const token = api.getToken();
      const res = await fetch(
        `/api/v1/projects/${projectId}/stories/${storyId}/capture-figma-images`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        },
      );
      if (!res.ok) throw new Error(await res.text());
      setResult(await res.json());
    } catch (e: any) {
      setError(String(e?.message || e));
    } finally {
      setCapturing(false);
    }
  };

  return (
    <div className="mb-6 rounded-lg border border-[var(--border)] bg-[var(--card)] p-4">
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-bold">Figma image capture</h2>
        <button
          onClick={capture}
          disabled={capturing}
          className="rounded-md bg-[var(--secondary)] px-3 py-1 text-xs hover:opacity-80 disabled:opacity-40"
        >
          {capturing ? "Capturing..." : "Capture frame images"}
        </button>
      </div>
      <p className="mt-1 text-xs text-[var(--muted-foreground)]">
        Fetch PNG renders of this story's Figma frame(s) and attach them so
        designers and agents have visual reference.
      </p>
      {error && (
        <div className="mt-2 rounded border border-red-500/30 bg-red-500/10 p-2 text-xs text-red-400">
          {error}
        </div>
      )}
      {result && (
        <div className="mt-2 rounded border border-green-500/30 bg-green-500/10 p-2 text-xs text-green-400">
          Captured {result.captured} image{result.captured === 1 ? "" : "s"} — see Attachments.
        </div>
      )}
    </div>
  );
}
