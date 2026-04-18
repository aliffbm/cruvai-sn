"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { api } from "@/lib/api";

export default function ProjectDetailPage() {
  const { id } = useParams<{ id: string }>();
  const [project, setProject] = useState<any>(null);
  const [stories, setStories] = useState<any[]>([]);
  const [jobs, setJobs] = useState<any[]>([]);
  const [tab, setTab] = useState<"stories" | "jobs" | "artifacts">("stories");

  useEffect(() => {
    if (!id) return;
    api.getProject(id).then(setProject);
    api.listStories(id).then(setStories);
    api.listJobs(id).then(setJobs);
  }, [id]);

  if (!project) return <div className="text-[var(--muted-foreground)]">Loading...</div>;

  const tabs = [
    { key: "stories", label: "Stories", count: stories.length },
    { key: "jobs", label: "Agent Jobs", count: jobs.length },
    { key: "artifacts", label: "Artifacts" },
  ];

  return (
    <div>
      <div className="mb-6 flex items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold">{project.name}</h1>
          <p className="mt-1 text-sm text-[var(--muted-foreground)]">{project.description}</p>
          <div className="mt-2 flex items-center gap-2 text-xs">
            {project.playbook_slug ? (
              <span className="rounded-full bg-[var(--primary)]/10 text-[var(--primary)] px-2 py-0.5">
                Playbook: {project.playbook_slug}
              </span>
            ) : (
              <span className="rounded-full bg-amber-500/10 text-amber-400 px-2 py-0.5">
                No playbook set
              </span>
            )}
            {project.figma_connector_id ? (
              <span className="rounded-full bg-[var(--primary)]/10 text-[var(--primary)] px-2 py-0.5">
                Figma connected
              </span>
            ) : (
              <span className="rounded-full bg-zinc-700 text-zinc-300 px-2 py-0.5">
                No Figma connector
              </span>
            )}
          </div>
        </div>
        <Link
          href={`/projects/${id}/settings`}
          className="rounded-lg border border-[var(--border)] px-3 py-1.5 text-sm hover:bg-[var(--secondary)]"
        >
          Settings
        </Link>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 border-b border-[var(--border)] mb-6">
        {tabs.map((t) => (
          <button
            key={t.key}
            onClick={() => setTab(t.key as any)}
            className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
              tab === t.key
                ? "border-[var(--primary)] text-[var(--primary)]"
                : "border-transparent text-[var(--muted-foreground)] hover:text-[var(--foreground)]"
            }`}
          >
            {t.label}
            {t.count !== undefined && (
              <span className="ml-1.5 rounded-full bg-[var(--secondary)] px-1.5 py-0.5 text-xs">
                {t.count}
              </span>
            )}
          </button>
        ))}
      </div>

      {/* Stories Tab */}
      {tab === "stories" && (
        <div className="space-y-3">
          <Link
            href={`/projects/${id}/stories`}
            className="inline-flex rounded-lg bg-[var(--primary)] px-4 py-2 text-sm font-medium text-[var(--primary-foreground)]"
          >
            Manage Stories
          </Link>

          {/* Epics — shown prominently */}
          {stories.filter((s) => s.story_type === "epic").map((epic) => {
            const children = stories.filter((s) => s.parent_story_id === epic.id);
            const doneCount = children.filter((s) => s.status === "done").length;
            return (
              <Link
                key={epic.id}
                href={`/projects/${id}/stories/${epic.id}`}
                className="block rounded-lg border-2 border-purple-500/30 bg-[var(--card)] p-5 hover:border-purple-500/60 transition-colors"
              >
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <span className="rounded bg-purple-500/20 text-purple-400 px-2 py-0.5 text-xs font-bold">EPIC</span>
                    <h3 className="font-bold text-lg">{epic.title}</h3>
                  </div>
                  <div className="flex items-center gap-3">
                    <span className="text-xs text-[var(--muted-foreground)]">{doneCount}/{children.length} stories</span>
                    <span className="rounded-full bg-[var(--secondary)] px-2 py-0.5 text-xs">{epic.status}</span>
                  </div>
                </div>
                <p className="mt-1.5 text-sm text-[var(--muted-foreground)] line-clamp-2">{epic.description}</p>
                {children.length > 0 && (
                  <div className="mt-3 h-1.5 rounded-full bg-[var(--secondary)]">
                    <div
                      className="h-full rounded-full bg-purple-500 transition-all"
                      style={{ width: `${children.length > 0 ? (doneCount / children.length) * 100 : 0}%` }}
                    />
                  </div>
                )}
              </Link>
            );
          })}

          {/* Standalone stories (no parent) */}
          {stories.filter((s) => s.story_type !== "epic" && !s.parent_story_id).map((story) => (
            <Link
              key={story.id}
              href={`/projects/${id}/stories/${story.id}`}
              className="block rounded-lg border border-[var(--border)] bg-[var(--card)] p-4 hover:border-[var(--primary)]/50 transition-colors"
            >
              <div className="flex items-center justify-between">
                <h3 className="font-medium">{story.title}</h3>
                <span className="rounded-full bg-[var(--secondary)] px-2 py-0.5 text-xs">{story.status}</span>
              </div>
              <p className="mt-1 text-sm text-[var(--muted-foreground)] line-clamp-2">{story.description}</p>
            </Link>
          ))}
        </div>
      )}

      {/* Jobs Tab */}
      {tab === "jobs" && (
        <div className="space-y-3">
          {jobs.map((job) => (
            <Link
              key={job.id}
              href={`/projects/${id}/jobs/${job.id}`}
              className="block rounded-lg border border-[var(--border)] bg-[var(--card)] p-4 hover:border-[var(--primary)]/50"
            >
              <div className="flex items-center justify-between">
                <span className="text-sm font-medium">Job {job.id.slice(0, 8)}</span>
                <span
                  className={`rounded-full px-2 py-0.5 text-xs ${
                    job.status === "completed"
                      ? "bg-green-500/10 text-green-400"
                      : job.status === "running"
                      ? "bg-blue-500/10 text-blue-400"
                      : job.status === "failed"
                      ? "bg-red-500/10 text-red-400"
                      : "bg-[var(--secondary)]"
                  }`}
                >
                  {job.status}
                </span>
              </div>
              {job.output_summary && (
                <p className="mt-2 text-sm text-[var(--muted-foreground)]">{job.output_summary}</p>
              )}
            </Link>
          ))}
        </div>
      )}

      {/* Artifacts Tab */}
      {tab === "artifacts" && (
        <Link
          href={`/projects/${id}/artifacts`}
          className="inline-flex rounded-lg bg-[var(--primary)] px-4 py-2 text-sm font-medium text-[var(--primary-foreground)]"
        >
          View All Artifacts
        </Link>
      )}
    </div>
  );
}
