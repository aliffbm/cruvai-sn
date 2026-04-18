"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { api } from "@/lib/api";

export default function ArtifactsPage() {
  const { id: projectId } = useParams<{ id: string }>();
  const [artifacts, setArtifacts] = useState<any[]>([]);
  const [selected, setSelected] = useState<any>(null);

  useEffect(() => {
    if (!projectId) return;
    api.listArtifacts(projectId).then(setArtifacts).catch(console.error);
  }, [projectId]);

  const typeColors: Record<string, string> = {
    catalog_item: "text-green-400",
    catalog_variable: "text-blue-400",
    business_rule: "text-yellow-400",
    client_script: "text-purple-400",
    ui_policy: "text-orange-400",
    flow: "text-cyan-400",
    atf_test: "text-pink-400",
  };

  return (
    <div className="flex gap-6 h-[calc(100vh-120px)]">
      {/* Artifact List */}
      <div className="w-96 flex flex-col">
        <h1 className="text-2xl font-bold mb-4">Artifacts</h1>
        <div className="flex-1 overflow-auto space-y-2">
          {artifacts.length === 0 && (
            <p className="text-sm text-[var(--muted-foreground)] text-center py-8">
              No artifacts yet. Launch an agent on a story to generate artifacts.
            </p>
          )}
          {artifacts.map((art) => (
            <button
              key={art.id}
              onClick={() => setSelected(art)}
              className={`w-full text-left rounded-lg border p-3 transition-colors ${
                selected?.id === art.id
                  ? "border-[var(--primary)] bg-[var(--primary)]/5"
                  : "border-[var(--border)] bg-[var(--card)] hover:border-[var(--primary)]/50"
              }`}
            >
              <div className="flex items-center justify-between">
                <span className={`text-xs font-medium ${typeColors[art.artifact_type] || ""}`}>
                  {art.artifact_type}
                </span>
                <span className="text-xs text-[var(--muted-foreground)]">{art.sn_table}</span>
              </div>
              <p className="mt-1 text-sm font-medium">{art.name}</p>
            </button>
          ))}
        </div>
      </div>

      {/* Artifact Detail */}
      <div className="flex-1 flex flex-col">
        {selected ? (
          <>
            <div className="mb-4">
              <h2 className="text-lg font-bold">{selected.name}</h2>
              <div className="flex gap-3 mt-1 text-xs text-[var(--muted-foreground)]">
                <span>Type: {selected.artifact_type}</span>
                <span>Table: {selected.sn_table}</span>
                <span>sys_id: {selected.sn_sys_id}</span>
              </div>
            </div>
            {selected.script_content ? (
              <div className="flex-1 overflow-auto rounded-lg border border-[var(--border)] bg-black/50 p-4">
                <pre className="text-sm font-mono text-green-400 whitespace-pre-wrap">
                  {selected.script_content}
                </pre>
              </div>
            ) : (
              <div className="flex-1 overflow-auto rounded-lg border border-[var(--border)] bg-[var(--card)] p-4">
                <pre className="text-sm font-mono text-[var(--muted-foreground)] whitespace-pre-wrap">
                  {JSON.stringify(selected.content_snapshot, null, 2)}
                </pre>
              </div>
            )}
          </>
        ) : (
          <div className="flex-1 flex items-center justify-center text-[var(--muted-foreground)]">
            Select an artifact to view its details
          </div>
        )}
      </div>
    </div>
  );
}
