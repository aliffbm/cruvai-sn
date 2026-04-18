"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { api } from "@/lib/api";

interface Version {
  id: string;
  version_number: number;
  content: string;
  authorship: string;
  derived_from_version_id: string | null;
  rewrite_summary: string | null;
  created_at: string;
}

interface Guidance {
  id: string;
  slug: string;
  name: string;
  description: string | null;
  license_type: string | null;
  requires_rewrite: boolean;
  has_cruvai_version: boolean;
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

export default function RewritePage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const guidanceId = params?.id ?? "";
  const [guidance, setGuidance] = useState<Guidance | null>(null);
  const [versions, setVersions] = useState<Version[]>([]);
  const [originalVersion, setOriginalVersion] = useState<Version | null>(null);
  const [draft, setDraft] = useState("");
  const [rewriteSummary, setRewriteSummary] = useState("");
  const [changeNotes, setChangeNotes] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!guidanceId) return;
    authedFetch<Guidance>(`/guidance/${guidanceId}`).then(setGuidance).catch((e) => setError(String(e)));
    authedFetch<Version[]>(`/guidance/${guidanceId}/versions`)
      .then((vs) => {
        setVersions(vs);
        const anthropic = vs.find((v) => v.authorship === "anthropic-toolkit");
        const base = anthropic ?? vs[vs.length - 1];
        if (base) {
          setOriginalVersion(base);
          setDraft(base.content);
        }
      })
      .catch((e) => setError(String(e)));
  }, [guidanceId]);

  const save = async () => {
    if (!guidance || !originalVersion) return;
    setSaving(true);
    setError(null);
    try {
      await authedFetch(`/guidance/${guidance.id}/versions`, {
        method: "POST",
        body: JSON.stringify({
          content: draft,
          authorship: "cruvai-authored",
          derived_from_version_id: originalVersion.id,
          rewrite_summary: rewriteSummary,
          change_notes: changeNotes,
        }),
      });
      router.push("/control-plane/toolkit");
    } catch (e: any) {
      setError(String(e?.message || e));
    } finally {
      setSaving(false);
    }
  };

  if (!guidance) {
    return <p className="text-[var(--muted-foreground)]">Loading…</p>;
  }

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-2xl font-bold">{guidance.name}</h1>
        <p className="text-sm text-[var(--muted-foreground)] mt-1 font-mono">{guidance.slug}</p>
        {guidance.license_type && (
          <p className="mt-1 text-xs text-amber-400">License: {guidance.license_type}</p>
        )}
        <p className="mt-2 text-sm">
          Produce a Cruvai-authored, enhanced version. Reuse methodology, but rewrite prose,
          replace examples with ServiceNow-specific ones, add enterprise concerns, and do not
          copy 15+ word contiguous spans from the original.
        </p>
      </div>

      {error && (
        <div className="rounded-lg border border-red-500/30 bg-red-500/10 p-3 text-sm text-red-400">
          {error}
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <div>
          <h2 className="text-sm font-medium mb-2">Original (read-only)</h2>
          <textarea
            readOnly
            value={originalVersion?.content ?? ""}
            rows={24}
            className="w-full rounded-md border border-[var(--border)] bg-[var(--card)] p-3 font-mono text-xs"
          />
        </div>
        <div>
          <h2 className="text-sm font-medium mb-2">Cruvai-authored (editable)</h2>
          <textarea
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            rows={24}
            className="w-full rounded-md border border-[var(--border)] bg-[var(--background)] p-3 font-mono text-xs focus:outline-none focus:ring-2 focus:ring-[var(--ring)]"
          />
        </div>
      </div>

      <div>
        <label className="block text-sm font-medium mb-1">
          Rewrite summary{" "}
          <span className="text-xs text-[var(--muted-foreground)]">
            — what you enhanced, in your words (IP defensibility artifact)
          </span>
        </label>
        <textarea
          value={rewriteSummary}
          onChange={(e) => setRewriteSummary(e.target.value)}
          rows={3}
          className="w-full rounded-md border border-[var(--border)] bg-[var(--background)] p-2 text-sm focus:outline-none focus:ring-2 focus:ring-[var(--ring)]"
        />
      </div>

      <div>
        <label className="block text-sm font-medium mb-1">Change notes</label>
        <input
          value={changeNotes}
          onChange={(e) => setChangeNotes(e.target.value)}
          className="w-full rounded-md border border-[var(--border)] bg-[var(--background)] p-2 text-sm focus:outline-none focus:ring-2 focus:ring-[var(--ring)]"
        />
      </div>

      <div className="flex gap-2">
        <button
          onClick={save}
          disabled={saving || !draft || !rewriteSummary}
          className="rounded-md bg-[var(--primary)] px-4 py-2 text-sm font-medium text-[var(--primary-foreground)] disabled:opacity-50"
        >
          {saving ? "Saving…" : "Save Cruvai-authored version"}
        </button>
        <button
          onClick={() => router.push("/control-plane/toolkit")}
          className="rounded-md border border-[var(--border)] px-4 py-2 text-sm"
        >
          Cancel
        </button>
      </div>
    </div>
  );
}
