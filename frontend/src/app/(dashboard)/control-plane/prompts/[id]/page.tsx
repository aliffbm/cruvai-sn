"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Markdown from "react-markdown";
import { api } from "@/lib/api";

interface Version {
  id: string;
  version_number: number;
  content: string;
  content_hash: string;
  change_notes: string | null;
  created_at: string;
}

interface PromptData {
  id: string;
  slug: string;
  name: string;
  description: string | null;
  agent_type: string | null;
  category: string;
  is_system: boolean;
  labels: Array<{ label: string; version_id: string }>;
}

export default function PromptDetailPage() {
  const { id } = useParams<{ id: string }>();
  const [prompt, setPrompt] = useState<PromptData | null>(null);
  const [versions, setVersions] = useState<Version[]>([]);
  const [selectedVersion, setSelectedVersion] = useState<Version | null>(null);
  const [editContent, setEditContent] = useState("");
  const [changeNotes, setChangeNotes] = useState("");
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState("");
  const [viewMode, setViewMode] = useState<"raw" | "rendered">("raw");

  useEffect(() => {
    if (!id) return;
    const token = api.getToken();
    const headers = { Authorization: `Bearer ${token}` };

    fetch(`/api/v1/control-plane/prompts/${id}`, { headers })
      .then((r) => r.json())
      .then(setPrompt);

    fetch(`/api/v1/control-plane/prompts/${id}/versions`, { headers })
      .then((r) => r.json())
      .then((vers: Version[]) => {
        setVersions(vers);
        if (vers.length > 0) {
          setSelectedVersion(vers[0]);
          setEditContent(vers[0].content);
        }
      });
  }, [id]);

  async function handleSaveVersion() {
    if (!id || !editContent.trim()) return;
    setSaving(true);
    setMessage("");
    try {
      const token = api.getToken();
      const res = await fetch(`/api/v1/control-plane/prompts/${id}/versions`, {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify({ content: editContent, change_notes: changeNotes || null }),
      });
      if (!res.ok) throw new Error(await res.text());
      const newVersion = await res.json();
      setVersions([newVersion, ...versions]);
      setSelectedVersion(newVersion);
      setChangeNotes("");
      setMessage(`Version ${newVersion.version_number} created`);
    } catch (err: any) {
      setMessage(`Error: ${err.message}`);
    } finally {
      setSaving(false);
    }
  }

  async function handlePromote(versionId: string, label: string) {
    const token = api.getToken();
    await fetch(`/api/v1/control-plane/prompts/${id}/labels`, {
      method: "POST",
      headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
      body: JSON.stringify({ version_id: versionId, label }),
    });
    // Reload prompt to get updated labels
    const res = await fetch(`/api/v1/control-plane/prompts/${id}`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    setPrompt(await res.json());
    setMessage(`Promoted to ${label}`);
  }

  if (!prompt) return <div className="text-[var(--muted-foreground)]">Loading...</div>;

  const productionLabel = prompt.labels?.find((l) => l.label === "production");
  const isContentChanged = selectedVersion && editContent !== selectedVersion.content;

  return (
    <div className="flex gap-6 h-[calc(100vh-120px)]">
      {/* Main Editor */}
      <div className="flex-1 flex flex-col">
        <div className="mb-4">
          <div className="flex items-center gap-3">
            <h1 className="text-xl font-bold">{prompt.name}</h1>
            {prompt.is_system && (
              <span className="rounded-full bg-zinc-700 px-2 py-0.5 text-xs">OOB</span>
            )}
            <span className="rounded-full bg-blue-500/20 text-blue-400 px-2 py-0.5 text-xs">
              {prompt.category}
            </span>
          </div>
          <p className="text-xs text-[var(--muted-foreground)] mt-1">
            {prompt.slug} {prompt.agent_type ? `| ${prompt.agent_type}` : "| shared"}
          </p>
        </div>

        {message && (
          <div className={`mb-3 rounded-lg p-2 text-xs ${message.startsWith("Error") ? "bg-red-500/10 text-red-400" : "bg-green-500/10 text-green-400"}`}>
            {message}
          </div>
        )}

        {/* View Mode Toggle + Editor/Renderer */}
        <div className="flex-1 flex flex-col">
          <div className="flex items-center gap-1 mb-2">
            <button
              onClick={() => setViewMode("raw")}
              className={`rounded px-3 py-1 text-xs font-medium transition-colors ${
                viewMode === "raw"
                  ? "bg-[var(--primary)] text-[var(--primary-foreground)]"
                  : "bg-[var(--secondary)] text-[var(--muted-foreground)] hover:text-[var(--foreground)]"
              }`}
            >
              Raw
            </button>
            <button
              onClick={() => setViewMode("rendered")}
              className={`rounded px-3 py-1 text-xs font-medium transition-colors ${
                viewMode === "rendered"
                  ? "bg-[var(--primary)] text-[var(--primary-foreground)]"
                  : "bg-[var(--secondary)] text-[var(--muted-foreground)] hover:text-[var(--foreground)]"
              }`}
            >
              Rendered
            </button>
          </div>

          {viewMode === "raw" ? (
            <textarea
              value={editContent}
              onChange={(e) => setEditContent(e.target.value)}
              className="flex-1 w-full rounded-lg border border-[var(--border)] bg-black/50 p-4 font-mono text-sm text-green-400 focus:outline-none focus:ring-2 focus:ring-[var(--ring)] resize-none"
              readOnly={prompt.is_system}
              placeholder="Prompt template content (supports Jinja2: {{ variable }})"
            />
          ) : (
            <div className="flex-1 overflow-auto rounded-lg border border-[var(--border)] bg-[var(--card)] p-6 prose prose-invert prose-sm max-w-none prose-headings:text-[var(--foreground)] prose-p:text-[var(--muted-foreground)] prose-strong:text-[var(--foreground)] prose-code:text-[var(--primary)] prose-code:bg-black/30 prose-code:rounded prose-code:px-1 prose-pre:bg-black/50 prose-pre:border prose-pre:border-[var(--border)] prose-li:text-[var(--muted-foreground)] prose-th:text-[var(--foreground)] prose-td:text-[var(--muted-foreground)] prose-table:border-collapse prose-th:border prose-th:border-[var(--border)] prose-th:px-3 prose-th:py-1.5 prose-td:border prose-td:border-[var(--border)] prose-td:px-3 prose-td:py-1.5">
              <Markdown>{editContent}</Markdown>
            </div>
          )}

          {!prompt.is_system && (
            <div className="mt-3 flex items-center gap-3">
              <input
                type="text"
                value={changeNotes}
                onChange={(e) => setChangeNotes(e.target.value)}
                placeholder="Change notes (optional)"
                className="flex-1 rounded-lg border border-[var(--border)] bg-[var(--card)] px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[var(--ring)]"
              />
              <button
                onClick={handleSaveVersion}
                disabled={saving || !isContentChanged}
                className="rounded-lg bg-[var(--primary)] px-4 py-2 text-sm font-medium text-[var(--primary-foreground)] hover:opacity-90 disabled:opacity-40"
              >
                {saving ? "Saving..." : "Save New Version"}
              </button>
            </div>
          )}
          {prompt.is_system && (
            <p className="mt-2 text-xs text-[var(--muted-foreground)]">
              System prompts are read-only. Fork by creating a custom prompt with the same slug.
            </p>
          )}
        </div>
      </div>

      {/* Version Sidebar */}
      <div className="w-72 flex flex-col">
        <h2 className="text-sm font-bold mb-3">Version History</h2>

        {/* Labels */}
        <div className="mb-4 space-y-1">
          {prompt.labels?.map((l) => (
            <div key={l.label} className="flex items-center justify-between rounded-lg bg-[var(--primary)]/5 border border-[var(--primary)]/20 px-3 py-1.5">
              <span className="text-xs font-medium text-[var(--primary)]">{l.label}</span>
              <span className="text-xs text-[var(--muted-foreground)]">
                → v{versions.find((v) => v.id === l.version_id)?.version_number || "?"}
              </span>
            </div>
          ))}
        </div>

        {/* Version List */}
        <div className="flex-1 overflow-auto space-y-1">
          {versions.map((v) => {
            const isProduction = productionLabel?.version_id === v.id;
            const isSelected = selectedVersion?.id === v.id;
            return (
              <button
                key={v.id}
                onClick={() => {
                  setSelectedVersion(v);
                  setEditContent(v.content);
                }}
                className={`w-full text-left rounded-lg border p-2 transition-colors ${
                  isSelected
                    ? "border-[var(--primary)] bg-[var(--primary)]/5"
                    : "border-[var(--border)] bg-[var(--card)] hover:border-[var(--primary)]/30"
                }`}
              >
                <div className="flex items-center justify-between">
                  <span className="text-xs font-medium">v{v.version_number}</span>
                  <div className="flex gap-1">
                    {isProduction && (
                      <span className="rounded bg-green-500/20 text-green-400 px-1 py-0.5 text-[10px]">
                        prod
                      </span>
                    )}
                    {!isProduction && (
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          handlePromote(v.id, "production");
                        }}
                        className="rounded bg-[var(--secondary)] px-1.5 py-0.5 text-[10px] hover:bg-[var(--primary)]/20"
                      >
                        promote
                      </button>
                    )}
                  </div>
                </div>
                {v.change_notes && (
                  <p className="text-[10px] text-[var(--muted-foreground)] mt-0.5 line-clamp-1">
                    {v.change_notes}
                  </p>
                )}
                <p className="text-[10px] text-[var(--muted-foreground)]">
                  {new Date(v.created_at).toLocaleDateString()}
                </p>
              </button>
            );
          })}
        </div>
      </div>
    </div>
  );
}
