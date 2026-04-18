"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { api } from "@/lib/api";

interface Project {
  id: string;
  name: string;
  description: string | null;
  status: string;
  instance_id: string | null;
  figma_connector_id: string | null;
  playbook_slug: string | null;
}

interface Connector {
  id: string;
  label: string;
  platform: string;
  status: string;
}

interface Playbook {
  id: string;
  slug: string;
  name: string;
  description: string | null;
}

async function authedFetch<T>(path: string, init: RequestInit = {}): Promise<T> {
  const token = api.getToken();
  const res = await fetch(`/api/v1${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(init.headers as Record<string, string> | undefined),
    },
  });
  if (!res.ok) throw new Error((await res.text()) || `Request failed: ${res.status}`);
  return res.json();
}

export default function ProjectSettingsPage() {
  const params = useParams<{ id: string }>();
  const projectId = params?.id ?? "";
  const [project, setProject] = useState<Project | null>(null);
  const [connectors, setConnectors] = useState<Connector[]>([]);
  const [playbooks, setPlaybooks] = useState<Playbook[]>([]);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!projectId) return;
    authedFetch<Project>(`/projects/${projectId}`).then(setProject).catch((e) => setError(String(e)));
    authedFetch<Connector[]>("/connectors").then(setConnectors).catch(() => {});
    authedFetch<Playbook[]>("/playbooks").then(setPlaybooks).catch(() => {});
  }, [projectId]);

  const figmaConnectors = connectors.filter((c) => c.platform === "figma");

  const save = async () => {
    if (!project) return;
    setSaving(true);
    setError(null);
    setMessage(null);
    try {
      const updated = await authedFetch<Project>(`/projects/${project.id}`, {
        method: "PATCH",
        body: JSON.stringify({
          figma_connector_id: project.figma_connector_id,
          playbook_slug: project.playbook_slug,
        }),
      });
      setProject(updated);
      setMessage("Saved.");
    } catch (e: any) {
      setError(String(e?.message || e));
    } finally {
      setSaving(false);
    }
  };

  if (!project) return <p className="text-[var(--muted-foreground)]">Loading…</p>;

  return (
    <div className="space-y-6 max-w-2xl">
      <div>
        <h1 className="text-2xl font-bold">{project.name}</h1>
        <p className="text-sm text-[var(--muted-foreground)] mt-1">Project settings</p>
      </div>

      {error && (
        <div className="rounded-lg border border-red-500/30 bg-red-500/10 p-3 text-sm text-red-400">
          {error}
        </div>
      )}
      {message && (
        <div className="rounded-lg border border-green-500/30 bg-green-500/10 p-3 text-sm text-green-400">
          {message}
        </div>
      )}

      <section className="rounded-lg border border-[var(--border)] bg-[var(--card)] p-4 space-y-3">
        <h2 className="font-medium">Figma</h2>
        <p className="text-sm text-[var(--muted-foreground)]">
          Select a Figma connector for this project. The Portal agent uses it to fetch
          designs referenced by the stories' Figma URLs.
        </p>
        <label className="block text-xs text-[var(--muted-foreground)]">Figma connector</label>
        <select
          value={project.figma_connector_id ?? ""}
          onChange={(e) =>
            setProject({ ...project, figma_connector_id: e.target.value || null })
          }
          className="w-full rounded-md border border-[var(--border)] bg-[var(--background)] px-2 py-1.5 text-sm"
        >
          <option value="">— none —</option>
          {figmaConnectors.map((c) => (
            <option key={c.id} value={c.id}>
              {c.label} ({c.status})
            </option>
          ))}
        </select>
        {figmaConnectors.length === 0 && (
          <p className="text-xs text-amber-400">
            No Figma connectors found.{" "}
            <a href="/connectors" className="underline">
              Create one
            </a>{" "}
            first.
          </p>
        )}
      </section>

      <section className="rounded-lg border border-[var(--border)] bg-[var(--card)] p-4 space-y-3">
        <h2 className="font-medium">Playbook</h2>
        <p className="text-sm text-[var(--muted-foreground)]">
          Pick a ServiceNow archetype playbook. When jobs are dispatched, matching routes
          pre-select supporting agents and force-inject required guidance.
        </p>
        <label className="block text-xs text-[var(--muted-foreground)]">Active playbook</label>
        <select
          value={project.playbook_slug ?? ""}
          onChange={(e) =>
            setProject({ ...project, playbook_slug: e.target.value || null })
          }
          className="w-full rounded-md border border-[var(--border)] bg-[var(--background)] px-2 py-1.5 text-sm"
        >
          <option value="">— none —</option>
          {playbooks.map((pb) => (
            <option key={pb.id} value={pb.slug}>
              {pb.name} ({pb.slug})
            </option>
          ))}
        </select>
      </section>

      <button
        onClick={save}
        disabled={saving}
        className="rounded-lg bg-[var(--primary)] px-4 py-2 text-sm font-medium text-[var(--primary-foreground)] disabled:opacity-50"
      >
        {saving ? "Saving…" : "Save"}
      </button>
    </div>
  );
}
