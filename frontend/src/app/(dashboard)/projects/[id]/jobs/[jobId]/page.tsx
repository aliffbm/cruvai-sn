"use client";

import { useEffect, useRef, useState } from "react";
import { useParams } from "next/navigation";
import { api } from "@/lib/api";

interface LogEntry {
  timestamp: string;
  level: string;
  message: string;
  metadata?: Record<string, unknown>;
}

export default function JobDetailPage() {
  const { id: projectId, jobId } = useParams<{ id: string; jobId: string }>();
  const [job, setJob] = useState<any>(null);
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [artifacts, setArtifacts] = useState<any[]>([]);
  const logsEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!projectId || !jobId) return;
    api.getJob(projectId, jobId).then(setJob);
    api.listArtifacts(projectId, jobId).then(setArtifacts);
  }, [projectId, jobId]);

  // SSE log stream
  useEffect(() => {
    if (!projectId || !jobId) return;
    const token = api.getToken();
    const eventSource = new EventSource(
      `/api/v1/projects/${projectId}/jobs/${jobId}/stream`
    );

    eventSource.onmessage = (event) => {
      try {
        const log: LogEntry = JSON.parse(event.data);
        setLogs((prev) => [...prev, log]);
      } catch {
        // ignore parse errors
      }
    };

    eventSource.onerror = () => {
      eventSource.close();
    };

    return () => eventSource.close();
  }, [projectId, jobId]);

  // Auto-scroll logs
  useEffect(() => {
    logsEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [logs]);

  if (!job) return <div className="text-[var(--muted-foreground)]">Loading...</div>;

  const levelColors: Record<string, string> = {
    info: "text-blue-400",
    warn: "text-yellow-400",
    error: "text-red-400",
    agent: "text-[var(--primary)]",
    debug: "text-[var(--muted-foreground)]",
  };

  return (
    <div className="flex gap-6 h-[calc(100vh-120px)]">
      {/* Log Stream */}
      <div className="flex-1 flex flex-col">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-bold">Agent Log</h2>
          <span
            className={`rounded-full px-3 py-1 text-xs font-medium ${
              job.status === "completed"
                ? "bg-green-500/10 text-green-400"
                : job.status === "running"
                ? "bg-blue-500/10 text-blue-400 animate-pulse"
                : job.status === "awaiting_approval"
                ? "bg-yellow-500/10 text-yellow-400"
                : job.status === "failed"
                ? "bg-red-500/10 text-red-400"
                : "bg-[var(--secondary)]"
            }`}
          >
            {job.status}
          </span>
        </div>

        {job.status === "awaiting_approval" && (
          <div className="mb-4 rounded-lg border border-yellow-500/30 bg-yellow-500/5 p-4">
            <p className="text-sm text-yellow-400 font-medium">Agent is awaiting your approval.</p>
            <div className="mt-3 flex gap-2">
              <button
                onClick={async () => {
                  await api.approveJob(projectId, jobId);
                  setJob({ ...job, status: "running" });
                }}
                className="rounded-lg bg-green-600 px-4 py-2 text-sm font-medium text-white"
              >
                Approve
              </button>
              <button className="rounded-lg border border-red-500/30 px-4 py-2 text-sm text-red-400">
                Reject
              </button>
            </div>
          </div>
        )}

        <div className="flex-1 overflow-auto rounded-lg border border-[var(--border)] bg-black/50 p-4 font-mono text-sm">
          {logs.length === 0 && (
            <p className="text-[var(--muted-foreground)]">Waiting for logs...</p>
          )}
          {logs.map((log, i) => (
            <div key={i} className="flex gap-3 py-0.5">
              <span className="text-[var(--muted-foreground)] text-xs whitespace-nowrap">
                {new Date(log.timestamp).toLocaleTimeString()}
              </span>
              <span className={`text-xs font-medium uppercase w-12 ${levelColors[log.level] || ""}`}>
                {log.level}
              </span>
              <span>{log.message}</span>
            </div>
          ))}
          <div ref={logsEndRef} />
        </div>
      </div>

      {/* Artifacts Panel */}
      <div className="w-80 flex flex-col">
        <h2 className="text-lg font-bold mb-4">Artifacts</h2>
        <div className="flex-1 overflow-auto space-y-2">
          {artifacts.length === 0 && (
            <p className="text-sm text-[var(--muted-foreground)]">No artifacts yet</p>
          )}
          {artifacts.map((art) => (
            <div
              key={art.id}
              className="rounded-lg border border-[var(--border)] bg-[var(--card)] p-3"
            >
              <div className="flex items-center justify-between">
                <span className="text-xs font-medium text-[var(--primary)]">{art.artifact_type}</span>
                <span className="text-xs text-[var(--muted-foreground)]">{art.sn_table}</span>
              </div>
              <p className="mt-1 text-sm font-medium">{art.name}</p>
              <p className="mt-0.5 text-xs text-[var(--muted-foreground)]">
                sys_id: {art.sn_sys_id?.slice(0, 16)}...
              </p>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
