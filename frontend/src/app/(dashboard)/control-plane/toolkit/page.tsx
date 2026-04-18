"use client";

import { useEffect, useMemo, useState } from "react";
import { api } from "@/lib/api";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface Guidance {
  id: string;
  slug: string;
  name: string;
  description: string | null;
  guidance_type: string;
  agent_types: string[] | null;
  source_origin: string;
  requires_rewrite: boolean;
  license_type: string | null;
  is_system: boolean;
  is_active: boolean;
  is_orphaned: boolean;
  has_cruvai_version: boolean;
  latest_version_number: number | null;
  labels: Array<{ label: string; version_id: string; traffic_weight: number }>;
}

interface Capability {
  id: string;
  primary_agent_id: string;
  specialist_agent_id: string;
  primary_slug: string | null;
  specialist_slug: string | null;
  delegation_context: string | null;
  trigger_keywords: string[];
  invocation_mode: string;
  priority: number;
  requires_approval: boolean;
  is_active: boolean;
}

interface Playbook {
  id: string;
  slug: string;
  name: string;
  description: string | null;
  source_origin: string;
  is_system: boolean;
  is_active: boolean;
  is_orphaned: boolean;
}

interface IngestionRun {
  id: string;
  started_at: string;
  finished_at: string | null;
  source_root: string | null;
  status: string;
  stats: Record<string, any> | null;
}

interface ComplianceRow {
  slug: string;
  name: string;
  license_type: string | null;
  has_cruvai_version: boolean;
  production_authorship: string | null;
  compliant: boolean;
}

type TabKey =
  | "guidance"
  | "rewrite-queue"
  | "capabilities"
  | "playbooks"
  | "ingestion"
  | "compliance"
  | "orphans";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

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

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

export default function ToolkitPage() {
  const [tab, setTab] = useState<TabKey>("guidance");
  const [guidance, setGuidance] = useState<Guidance[]>([]);
  const [capabilities, setCapabilities] = useState<Capability[]>([]);
  const [playbooks, setPlaybooks] = useState<Playbook[]>([]);
  const [runs, setRuns] = useState<IngestionRun[]>([]);
  const [compliance, setCompliance] = useState<ComplianceRow[]>([]);
  const [filter, setFilter] = useState("");
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const reloadAll = () => {
    authedFetch<Guidance[]>("/guidance").then(setGuidance).catch((e) => setError(String(e)));
    authedFetch<Capability[]>("/capabilities").then(setCapabilities).catch(() => {});
    authedFetch<Playbook[]>("/playbooks").then(setPlaybooks).catch(() => {});
    authedFetch<IngestionRun[]>("/ingestion").then(setRuns).catch(() => {});
    authedFetch<ComplianceRow[]>("/guidance/compliance/licensed-guidance")
      .then(setCompliance)
      .catch(() => {});
  };

  useEffect(reloadAll, []);

  const rewriteQueue = useMemo(
    () => guidance.filter((g) => g.requires_rewrite && !g.has_cruvai_version),
    [guidance],
  );
  const orphans = useMemo(() => guidance.filter((g) => g.is_orphaned), [guidance]);
  const filteredGuidance = useMemo(
    () =>
      guidance.filter(
        (g) =>
          !filter ||
          g.slug.toLowerCase().includes(filter.toLowerCase()) ||
          g.name.toLowerCase().includes(filter.toLowerCase()),
      ),
    [guidance, filter],
  );

  const triggerIngest = async () => {
    if (!confirm("Run toolkit ingestion now? This may create new guidance versions.")) return;
    setBusy("ingest");
    setError(null);
    try {
      await authedFetch<{ status: string }>("/ingestion/trigger", {
        method: "POST",
        body: JSON.stringify({}),
      });
      setTimeout(reloadAll, 1500);
    } catch (e: any) {
      setError(String(e?.message || e));
    } finally {
      setBusy(null);
    }
  };

  const promoteLabel = async (guidanceId: string, versionId: string, label: string) => {
    setBusy(`promote-${guidanceId}-${label}`);
    setError(null);
    try {
      await authedFetch(`/guidance/${guidanceId}/labels`, {
        method: "POST",
        body: JSON.stringify({ version_id: versionId, label, traffic_weight: 100 }),
      });
      reloadAll();
    } catch (e: any) {
      setError(String(e?.message || e));
    } finally {
      setBusy(null);
    }
  };

  const tabDefs: { key: TabKey; label: string; count: number }[] = [
    { key: "guidance", label: "Guidance Library", count: guidance.length },
    { key: "rewrite-queue", label: "Rewrite Queue", count: rewriteQueue.length },
    { key: "capabilities", label: "Capabilities", count: capabilities.length },
    { key: "playbooks", label: "Playbooks", count: playbooks.length },
    { key: "ingestion", label: "Ingestion Runs", count: runs.length },
    { key: "compliance", label: "IP Compliance", count: compliance.length },
    { key: "orphans", label: "Orphans", count: orphans.length },
  ];

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold">Toolkit</h1>
          <p className="text-sm text-[var(--muted-foreground)] mt-1">
            Governed guidance, specialist delegation, and ServiceNow archetype playbooks
          </p>
        </div>
        <button
          onClick={triggerIngest}
          disabled={busy === "ingest"}
          className="rounded-lg bg-[var(--primary)] px-4 py-2 text-sm font-medium text-[var(--primary-foreground)] hover:opacity-90 disabled:opacity-50"
        >
          {busy === "ingest" ? "Running…" : "Run ingest now"}
        </button>
      </div>

      {error && (
        <div className="mb-4 rounded-lg border border-red-500/30 bg-red-500/10 p-3 text-sm text-red-400">
          {error}
        </div>
      )}

      <div className="flex items-center justify-between border-b border-[var(--border)] mb-6">
        <div className="flex gap-1 overflow-x-auto">
          {tabDefs.map((t) => (
            <button
              key={t.key}
              onClick={() => setTab(t.key)}
              className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors whitespace-nowrap ${
                tab === t.key
                  ? "border-[var(--primary)] text-[var(--primary)]"
                  : "border-transparent text-[var(--muted-foreground)] hover:text-[var(--foreground)]"
              }`}
            >
              {t.label}
              <span className="ml-1.5 rounded-full bg-[var(--secondary)] px-1.5 py-0.5 text-xs">
                {t.count}
              </span>
            </button>
          ))}
        </div>
        {tab === "guidance" && (
          <input
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
            placeholder="Filter…"
            className="rounded-lg border border-[var(--border)] bg-[var(--card)] px-3 py-1.5 text-xs focus:outline-none focus:ring-2 focus:ring-[var(--ring)]"
          />
        )}
      </div>

      {tab === "guidance" && (
        <GuidanceList
          items={filteredGuidance}
          onPromote={promoteLabel}
          busy={busy}
        />
      )}
      {tab === "rewrite-queue" && <RewriteQueue items={rewriteQueue} />}
      {tab === "capabilities" && <CapabilitiesList items={capabilities} />}
      {tab === "playbooks" && <PlaybooksPanel playbooks={playbooks} onReload={reloadAll} />}
      {tab === "ingestion" && <RunsList runs={runs} />}
      {tab === "compliance" && <ComplianceList rows={compliance} />}
      {tab === "orphans" && <OrphansList items={orphans} />}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Guidance List
// ---------------------------------------------------------------------------

function GuidanceList({
  items,
  onPromote,
  busy,
}: {
  items: Guidance[];
  onPromote: (gid: string, vid: string, label: string) => void;
  busy: string | null;
}) {
  if (items.length === 0) {
    return (
      <p className="text-[var(--muted-foreground)] text-center py-8">
        No guidance found. Trigger an ingest to load the toolkit.
      </p>
    );
  }
  return (
    <div className="space-y-2">
      {items.map((g) => (
        <div
          key={g.id}
          className="rounded-lg border border-[var(--border)] bg-[var(--card)] p-4"
        >
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2 flex-wrap">
              <h3 className="font-medium">{g.name}</h3>
              <span className="text-xs text-[var(--muted-foreground)] font-mono">{g.slug}</span>
              {g.is_system && (
                <span className="rounded-full bg-zinc-700 px-2 py-0.5 text-xs text-zinc-300">
                  OOB
                </span>
              )}
              {g.is_orphaned && (
                <span className="rounded-full bg-red-500/20 px-2 py-0.5 text-xs text-red-400">
                  orphaned
                </span>
              )}
              {g.requires_rewrite && (
                <span className="rounded-full bg-amber-500/20 px-2 py-0.5 text-xs text-amber-400">
                  requires rewrite
                </span>
              )}
              <span className="rounded-full bg-blue-500/20 px-2 py-0.5 text-xs text-blue-400">
                {g.guidance_type}
              </span>
            </div>
            <div className="flex items-center gap-2">
              {g.labels?.map((l) => (
                <span
                  key={l.label}
                  className="rounded-full bg-[var(--primary)]/10 text-[var(--primary)] px-2 py-0.5 text-xs"
                >
                  {l.label} · {l.traffic_weight}%
                </span>
              ))}
              {g.latest_version_number && (
                <span className="text-xs text-[var(--muted-foreground)]">
                  v{g.latest_version_number}
                </span>
              )}
            </div>
          </div>
          {g.description && (
            <p className="mt-1 text-sm text-[var(--muted-foreground)] line-clamp-2">
              {g.description}
            </p>
          )}
          <div className="mt-2 flex gap-2">
            {g.labels?.find((l) => l.label === "staging") && !g.requires_rewrite && (
              <button
                onClick={() =>
                  onPromote(
                    g.id,
                    g.labels.find((l) => l.label === "staging")!.version_id,
                    "production",
                  )
                }
                disabled={busy !== null}
                className="rounded-md bg-[var(--secondary)] px-2 py-1 text-xs hover:bg-[var(--secondary)]/80 disabled:opacity-50"
              >
                Promote staging → production
              </button>
            )}
            {g.requires_rewrite && !g.has_cruvai_version && (
              <span className="text-xs text-amber-400">
                Production promotion blocked — needs Cruvai-authored version
              </span>
            )}
          </div>
        </div>
      ))}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Rewrite Queue
// ---------------------------------------------------------------------------

function RewriteQueue({ items }: { items: Guidance[] }) {
  if (items.length === 0) {
    return (
      <p className="text-[var(--muted-foreground)] text-center py-8">
        Nothing pending. All licensed guidance has a Cruvai-authored version.
      </p>
    );
  }
  return (
    <div className="space-y-2">
      {items.map((g) => (
        <div
          key={g.id}
          className="rounded-lg border border-amber-500/30 bg-amber-500/5 p-4"
        >
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2 flex-wrap">
              <h3 className="font-medium">{g.name}</h3>
              <span className="text-xs text-[var(--muted-foreground)] font-mono">{g.slug}</span>
              {g.license_type && (
                <span className="rounded-full bg-amber-500/20 px-2 py-0.5 text-xs text-amber-400">
                  {g.license_type}
                </span>
              )}
            </div>
            <a
              href={`/control-plane/toolkit/guidance/${g.id}/rewrite`}
              className="rounded-md bg-[var(--primary)] px-3 py-1 text-xs text-[var(--primary-foreground)] hover:opacity-90"
            >
              Start rewrite
            </a>
          </div>
          {g.description && (
            <p className="mt-1 text-sm text-[var(--muted-foreground)] line-clamp-2">{g.description}</p>
          )}
        </div>
      ))}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Capabilities
// ---------------------------------------------------------------------------

function CapabilitiesList({ items }: { items: Capability[] }) {
  if (items.length === 0) {
    return (
      <p className="text-[var(--muted-foreground)] text-center py-8">
        No delegation capabilities defined. Add capabilities to let primary agents delegate
        to specialists.
      </p>
    );
  }
  return (
    <div className="space-y-2">
      {items.map((c) => (
        <div
          key={c.id}
          className="rounded-lg border border-[var(--border)] bg-[var(--card)] p-4"
        >
          <div className="flex items-center gap-2 flex-wrap">
            <span className="font-mono text-xs text-[var(--muted-foreground)]">P{c.priority}</span>
            <span className="font-medium">{c.primary_slug || c.primary_agent_id}</span>
            <span className="text-[var(--muted-foreground)]">→</span>
            <span className="font-medium">{c.specialist_slug || c.specialist_agent_id}</span>
            <span className="rounded-full bg-blue-500/20 px-2 py-0.5 text-xs text-blue-400">
              {c.invocation_mode}
            </span>
            {!c.is_active && (
              <span className="rounded-full bg-red-500/20 px-2 py-0.5 text-xs text-red-400">
                disabled
              </span>
            )}
          </div>
          {c.delegation_context && (
            <p className="mt-1 text-sm text-[var(--muted-foreground)]">{c.delegation_context}</p>
          )}
          {c.trigger_keywords.length > 0 && (
            <p className="mt-1 text-xs text-[var(--muted-foreground)]">
              Triggers: {c.trigger_keywords.join(", ")}
            </p>
          )}
        </div>
      ))}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Playbooks + simulator
// ---------------------------------------------------------------------------

function PlaybooksPanel({
  playbooks,
  onReload,
}: {
  playbooks: Playbook[];
  onReload: () => void;
}) {
  const [simSlug, setSimSlug] = useState("");
  const [simTitle, setSimTitle] = useState("");
  const [simDesc, setSimDesc] = useState("");
  const [simResult, setSimResult] = useState<any>(null);
  const [simError, setSimError] = useState<string | null>(null);

  const runSim = async () => {
    setSimError(null);
    setSimResult(null);
    try {
      const res = await authedFetch<any>("/playbooks/simulate", {
        method: "POST",
        body: JSON.stringify({
          playbook_slug: simSlug,
          story_title: simTitle,
          story_description: simDesc,
        }),
      });
      setSimResult(res);
    } catch (e: any) {
      setSimError(String(e?.message || e));
    }
  };

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
      <div className="space-y-2">
        <h2 className="text-sm font-medium text-[var(--muted-foreground)]">Playbooks</h2>
        {playbooks.length === 0 && (
          <p className="text-[var(--muted-foreground)] text-sm">
            No playbooks ingested yet.
          </p>
        )}
        {playbooks.map((pb) => (
          <div
            key={pb.id}
            className="rounded-lg border border-[var(--border)] bg-[var(--card)] p-4"
          >
            <div className="flex items-center gap-2">
              <h3 className="font-medium">{pb.name}</h3>
              <span className="text-xs text-[var(--muted-foreground)] font-mono">{pb.slug}</span>
              {pb.is_system && (
                <span className="rounded-full bg-zinc-700 px-2 py-0.5 text-xs text-zinc-300">
                  OOB
                </span>
              )}
            </div>
            {pb.description && (
              <p className="mt-1 text-sm text-[var(--muted-foreground)] line-clamp-2">
                {pb.description}
              </p>
            )}
          </div>
        ))}
      </div>

      <div className="rounded-lg border border-[var(--border)] bg-[var(--card)] p-4">
        <h2 className="text-sm font-medium mb-3">Route Simulator</h2>
        <label className="block text-xs text-[var(--muted-foreground)]">Playbook</label>
        <select
          value={simSlug}
          onChange={(e) => setSimSlug(e.target.value)}
          className="w-full rounded-md border border-[var(--border)] bg-[var(--background)] px-2 py-1 text-sm"
        >
          <option value="">— select —</option>
          {playbooks.map((pb) => (
            <option key={pb.id} value={pb.slug}>
              {pb.slug}
            </option>
          ))}
        </select>
        <label className="block text-xs text-[var(--muted-foreground)] mt-3">Story title</label>
        <input
          value={simTitle}
          onChange={(e) => setSimTitle(e.target.value)}
          className="w-full rounded-md border border-[var(--border)] bg-[var(--background)] px-2 py-1 text-sm"
        />
        <label className="block text-xs text-[var(--muted-foreground)] mt-3">Story description</label>
        <textarea
          value={simDesc}
          onChange={(e) => setSimDesc(e.target.value)}
          rows={4}
          className="w-full rounded-md border border-[var(--border)] bg-[var(--background)] px-2 py-1 text-sm"
        />
        <button
          onClick={runSim}
          disabled={!simSlug || !simTitle}
          className="mt-3 rounded-md bg-[var(--primary)] px-3 py-1.5 text-sm text-[var(--primary-foreground)] disabled:opacity-50"
        >
          Simulate
        </button>
        {simError && <p className="mt-2 text-xs text-red-400">{simError}</p>}
        {simResult && (
          <pre className="mt-3 rounded-md bg-black/40 p-2 text-xs overflow-x-auto">
            {JSON.stringify(simResult, null, 2)}
          </pre>
        )}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Runs
// ---------------------------------------------------------------------------

function RunsList({ runs }: { runs: IngestionRun[] }) {
  if (runs.length === 0) {
    return (
      <p className="text-[var(--muted-foreground)] text-center py-8">
        No ingestion runs yet. Click "Run ingest now" to start one.
      </p>
    );
  }
  return (
    <div className="space-y-2">
      {runs.map((r) => (
        <div
          key={r.id}
          className="rounded-lg border border-[var(--border)] bg-[var(--card)] p-4"
        >
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <span className="font-mono text-xs">{new Date(r.started_at).toLocaleString()}</span>
              <span
                className={`rounded-full px-2 py-0.5 text-xs ${
                  r.status === "succeeded"
                    ? "bg-green-500/20 text-green-400"
                    : r.status === "failed"
                    ? "bg-red-500/20 text-red-400"
                    : r.status === "partial"
                    ? "bg-amber-500/20 text-amber-400"
                    : "bg-blue-500/20 text-blue-400"
                }`}
              >
                {r.status}
              </span>
            </div>
            <span className="text-xs text-[var(--muted-foreground)] font-mono">
              {r.source_root || "—"}
            </span>
          </div>
          {r.stats && (
            <pre className="mt-2 rounded-md bg-black/40 p-2 text-xs overflow-x-auto">
              {JSON.stringify(r.stats, null, 2)}
            </pre>
          )}
        </div>
      ))}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Compliance
// ---------------------------------------------------------------------------

function ComplianceList({ rows }: { rows: ComplianceRow[] }) {
  if (rows.length === 0) {
    return (
      <p className="text-[var(--muted-foreground)] text-center py-8">
        No licensed guidance found.
      </p>
    );
  }
  return (
    <div className="rounded-lg border border-[var(--border)] overflow-hidden">
      <table className="w-full text-sm">
        <thead>
          <tr className="bg-[var(--card)] border-b border-[var(--border)] text-left">
            <th className="px-3 py-2 text-xs font-medium text-[var(--muted-foreground)]">Slug</th>
            <th className="px-3 py-2 text-xs font-medium text-[var(--muted-foreground)]">Name</th>
            <th className="px-3 py-2 text-xs font-medium text-[var(--muted-foreground)]">License</th>
            <th className="px-3 py-2 text-xs font-medium text-[var(--muted-foreground)]">
              Cruvai version
            </th>
            <th className="px-3 py-2 text-xs font-medium text-[var(--muted-foreground)]">
              Production authorship
            </th>
            <th className="px-3 py-2 text-xs font-medium text-[var(--muted-foreground)]">
              Compliant
            </th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr
              key={r.slug}
              className="border-b border-[var(--border)] hover:bg-[var(--card)]"
            >
              <td className="px-3 py-2 font-mono text-xs">{r.slug}</td>
              <td className="px-3 py-2 text-sm">{r.name}</td>
              <td className="px-3 py-2 text-xs text-[var(--muted-foreground)]">
                {r.license_type || "—"}
              </td>
              <td className="px-3 py-2 text-xs">{r.has_cruvai_version ? "✓" : "—"}</td>
              <td className="px-3 py-2 text-xs">{r.production_authorship || "—"}</td>
              <td className="px-3 py-2">
                <span
                  className={`rounded-full px-2 py-0.5 text-xs ${
                    r.compliant
                      ? "bg-green-500/20 text-green-400"
                      : "bg-red-500/20 text-red-400"
                  }`}
                >
                  {r.compliant ? "yes" : "no"}
                </span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Orphans
// ---------------------------------------------------------------------------

function OrphansList({ items }: { items: Guidance[] }) {
  if (items.length === 0) {
    return (
      <p className="text-[var(--muted-foreground)] text-center py-8">
        No orphaned guidance detected.
      </p>
    );
  }
  return (
    <div className="space-y-2">
      {items.map((g) => (
        <div
          key={g.id}
          className="rounded-lg border border-red-500/30 bg-red-500/5 p-4"
        >
          <div className="flex items-center gap-2 flex-wrap">
            <h3 className="font-medium">{g.name}</h3>
            <span className="text-xs text-[var(--muted-foreground)] font-mono">{g.slug}</span>
            <span className="rounded-full bg-red-500/20 px-2 py-0.5 text-xs text-red-400">
              orphaned
            </span>
          </div>
          <p className="mt-1 text-xs text-[var(--muted-foreground)]">
            Source no longer present in the toolkit tree. Review whether this was renamed
            upstream (match by content hash in the API) or intentionally removed.
          </p>
        </div>
      ))}
    </div>
  );
}
