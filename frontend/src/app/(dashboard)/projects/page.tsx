"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { api } from "@/lib/api";

export default function ProjectsPage() {
  const [projects, setProjects] = useState<any[]>([]);
  const [showCreate, setShowCreate] = useState(false);
  const [newProject, setNewProject] = useState({ name: "", description: "" });

  useEffect(() => {
    api.listProjects().then(setProjects).catch(console.error);
  }, []);

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    const created = await api.createProject(newProject);
    setProjects([...projects, created]);
    setShowCreate(false);
    setNewProject({ name: "", description: "" });
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold">Projects</h1>
        <button
          onClick={() => setShowCreate(true)}
          className="rounded-lg bg-[var(--primary)] px-4 py-2 text-sm font-medium text-[var(--primary-foreground)] hover:opacity-90"
        >
          New Project
        </button>
      </div>

      {showCreate && (
        <form onSubmit={handleCreate} className="mb-6 rounded-lg border border-[var(--border)] bg-[var(--card)] p-4 space-y-3">
          <input
            type="text"
            placeholder="Project name"
            value={newProject.name}
            onChange={(e) => setNewProject({ ...newProject, name: e.target.value })}
            className="w-full rounded-lg border border-[var(--border)] bg-[var(--background)] px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[var(--ring)]"
            required
          />
          <textarea
            placeholder="Description (optional)"
            value={newProject.description}
            onChange={(e) => setNewProject({ ...newProject, description: e.target.value })}
            className="w-full rounded-lg border border-[var(--border)] bg-[var(--background)] px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[var(--ring)]"
            rows={2}
          />
          <div className="flex gap-2">
            <button type="submit" className="rounded-lg bg-[var(--primary)] px-4 py-2 text-sm font-medium text-[var(--primary-foreground)]">
              Create
            </button>
            <button type="button" onClick={() => setShowCreate(false)} className="rounded-lg border border-[var(--border)] px-4 py-2 text-sm">
              Cancel
            </button>
          </div>
        </form>
      )}

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {projects.map((project) => (
          <Link
            key={project.id}
            href={`/projects/${project.id}`}
            className="rounded-lg border border-[var(--border)] bg-[var(--card)] p-4 hover:border-[var(--primary)]/50 transition-colors"
          >
            <h3 className="font-semibold">{project.name}</h3>
            <p className="mt-1 text-sm text-[var(--muted-foreground)] line-clamp-2">
              {project.description || "No description"}
            </p>
            <div className="mt-3 flex items-center gap-2">
              <span className="inline-flex rounded-full bg-[var(--secondary)] px-2 py-0.5 text-xs">
                {project.status}
              </span>
            </div>
          </Link>
        ))}
        {projects.length === 0 && !showCreate && (
          <p className="text-[var(--muted-foreground)] col-span-full text-center py-12">
            No projects yet. Create your first project to get started.
          </p>
        )}
      </div>
    </div>
  );
}
