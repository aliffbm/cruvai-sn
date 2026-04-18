"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { api } from "@/lib/api";

interface Prompt {
  id: string;
  slug: string;
  name: string;
  description: string | null;
  agent_type: string | null;
  category: string;
  is_system: boolean;
  labels: Array<{ label: string; version_id: string; is_active: boolean }>;
  latest_version_number: number | null;
}

interface Skill {
  id: string;
  slug: string;
  name: string;
  description: string | null;
  agent_type: string | null;
  is_system: boolean;
  steps: Array<{ step_number: number; name: string; step_type: string }>;
}

type TabKey = "prompts" | "skills" | "models" | "routing" | "logs" | "spend";

export default function ControlPlanePage() {
  const [tab, setTab] = useState<TabKey>("prompts");
  const [prompts, setPrompts] = useState<Prompt[]>([]);
  const [skills, setSkills] = useState<Skill[]>([]);
  const [models, setModels] = useState<any[]>([]);
  const [rules, setRules] = useState<any[]>([]);
  const [logs, setLogs] = useState<any[]>([]);
  const [spend, setSpend] = useState<any[]>([]);
  const [filter, setFilter] = useState("");

  useEffect(() => {
    const token = api.getToken();
    const headers = { Authorization: `Bearer ${token}` };

    fetch("/api/v1/control-plane/prompts", { headers })
      .then((r) => (r.ok ? r.json() : []))
      .then(setPrompts)
      .catch(() => {});

    fetch("/api/v1/control-plane/skills", { headers })
      .then((r) => (r.ok ? r.json() : []))
      .then(setSkills)
      .catch(() => {});

    api.listModelConfigs().then(setModels).catch(() => {});
    api.listRequestLogs({ limit: 50 }).then(setLogs).catch(() => {});
    api.listMonthlySpend().then(setSpend).catch(() => {});

    fetch("/api/v1/control-plane/routing-rules", { headers })
      .then((r) => (r.ok ? r.json() : []))
      .then(setRules)
      .catch(() => {});
  }, []);

  const categoryColors: Record<string, string> = {
    system: "bg-blue-500/20 text-blue-400",
    shared_context: "bg-green-500/20 text-green-400",
    task: "bg-purple-500/20 text-purple-400",
    analysis: "bg-orange-500/20 text-orange-400",
  };

  const stepTypeColors: Record<string, string> = {
    tool_call: "bg-cyan-500/20 text-cyan-400",
    llm_call: "bg-purple-500/20 text-purple-400",
    sub_skill: "bg-orange-500/20 text-orange-400",
    loop: "bg-yellow-500/20 text-yellow-400",
    conditional: "bg-pink-500/20 text-pink-400",
  };

  const filteredPrompts = prompts.filter(
    (p) => !filter || p.agent_type === filter || (!p.agent_type && filter === "shared")
  );
  const filteredSkills = skills.filter(
    (s) => !filter || s.agent_type === filter
  );

  const agentTypes = [...new Set(prompts.map((p) => p.agent_type).filter(Boolean))];

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold">AI Control Plane</h1>
          <p className="text-sm text-[var(--muted-foreground)] mt-1">
            Manage versioned prompts and skills for all agents
          </p>
        </div>
      </div>

      {/* Tabs + Filter */}
      <div className="flex items-center justify-between border-b border-[var(--border)] mb-6">
        <div className="flex gap-1 overflow-x-auto">
          {(
            [
              { key: "prompts", count: prompts.length },
              { key: "skills", count: skills.length },
              { key: "models", count: models.length },
              { key: "routing", count: rules.length },
              { key: "logs", count: logs.length },
              { key: "spend", count: spend.length },
            ] as { key: TabKey; count: number }[]
          ).map((t) => (
            <button
              key={t.key}
              onClick={() => setTab(t.key)}
              className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors capitalize whitespace-nowrap ${
                tab === t.key
                  ? "border-[var(--primary)] text-[var(--primary)]"
                  : "border-transparent text-[var(--muted-foreground)] hover:text-[var(--foreground)]"
              }`}
            >
              {t.key}
              <span className="ml-1.5 rounded-full bg-[var(--secondary)] px-1.5 py-0.5 text-xs">
                {t.count}
              </span>
            </button>
          ))}
        </div>
        <select
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
          className="rounded-lg border border-[var(--border)] bg-[var(--card)] px-3 py-1.5 text-xs focus:outline-none focus:ring-2 focus:ring-[var(--ring)]"
        >
          <option value="">All agent types</option>
          <option value="shared">Shared</option>
          {agentTypes.map((t) => (
            <option key={t} value={t!}>
              {t}
            </option>
          ))}
        </select>
      </div>

      {/* Prompts Tab */}
      {tab === "prompts" && (
        <div className="space-y-2">
          {filteredPrompts.map((p) => (
            <Link
              key={p.id}
              href={`/control-plane/prompts/${p.id}`}
              className="block rounded-lg border border-[var(--border)] bg-[var(--card)] p-4 hover:border-[var(--primary)]/50 transition-colors"
            >
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <h3 className="font-medium">{p.name}</h3>
                  {p.is_system && (
                    <span className="rounded-full bg-zinc-700 px-2 py-0.5 text-xs text-zinc-300">
                      OOB
                    </span>
                  )}
                  <span className={`rounded-full px-2 py-0.5 text-xs ${categoryColors[p.category] || "bg-zinc-700"}`}>
                    {p.category}
                  </span>
                  {p.agent_type && (
                    <span className="text-xs text-[var(--muted-foreground)]">
                      {p.agent_type}
                    </span>
                  )}
                </div>
                <div className="flex items-center gap-2">
                  {p.labels?.map((l) => (
                    <span
                      key={l.label}
                      className="rounded-full bg-[var(--primary)]/10 text-[var(--primary)] px-2 py-0.5 text-xs"
                    >
                      {l.label}
                    </span>
                  ))}
                  {p.latest_version_number && (
                    <span className="text-xs text-[var(--muted-foreground)]">
                      v{p.latest_version_number}
                    </span>
                  )}
                </div>
              </div>
              <p className="mt-1 text-sm text-[var(--muted-foreground)] line-clamp-1">
                {p.description || p.slug}
              </p>
            </Link>
          ))}
          {filteredPrompts.length === 0 && (
            <p className="text-[var(--muted-foreground)] text-center py-8">
              No prompts found. Run the seed script to create OOB prompts.
            </p>
          )}
        </div>
      )}

      {/* Skills Tab */}
      {tab === "skills" && (
        <div className="space-y-2">
          {filteredSkills.map((s) => (
            <Link
              key={s.id}
              href={`/control-plane/skills/${s.id}`}
              className="block rounded-lg border border-[var(--border)] bg-[var(--card)] p-4 hover:border-[var(--primary)]/50 transition-colors"
            >
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <h3 className="font-medium">{s.name}</h3>
                  {s.is_system && (
                    <span className="rounded-full bg-zinc-700 px-2 py-0.5 text-xs text-zinc-300">
                      OOB
                    </span>
                  )}
                  {s.agent_type && (
                    <span className="text-xs text-[var(--muted-foreground)]">{s.agent_type}</span>
                  )}
                </div>
                <span className="text-xs text-[var(--muted-foreground)]">
                  {s.steps?.length || 0} steps
                </span>
              </div>
              {s.steps && s.steps.length > 0 && (
                <div className="mt-2 flex flex-wrap gap-1">
                  {s.steps.map((step, i) => (
                    <span
                      key={i}
                      className={`rounded px-1.5 py-0.5 text-xs ${stepTypeColors[step.step_type] || "bg-zinc-700"}`}
                    >
                      {step.step_number}. {step.name}
                    </span>
                  ))}
                </div>
              )}
              <p className="mt-1 text-sm text-[var(--muted-foreground)] line-clamp-1">
                {s.description || s.slug}
              </p>
            </Link>
          ))}
          {filteredSkills.length === 0 && (
            <p className="text-[var(--muted-foreground)] text-center py-8">
              No skills found. Run the seed script to create OOB skills.
            </p>
          )}
        </div>
      )}

      {/* Models Tab */}
      {tab === "models" && (
        <div className="space-y-2">
          {models.map((m) => (
            <div key={m.id} className="rounded-lg border border-[var(--border)] bg-[var(--card)] p-4">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <h3 className="font-medium">{m.display_name}</h3>
                  <span className="rounded-full bg-blue-500/20 text-blue-400 px-2 py-0.5 text-xs">
                    {m.provider}
                  </span>
                  {!m.is_active && (
                    <span className="rounded-full bg-red-500/20 text-red-400 px-2 py-0.5 text-xs">
                      disabled
                    </span>
                  )}
                </div>
                <span className="text-xs text-[var(--muted-foreground)] font-mono">{m.model_id}</span>
              </div>
              <div className="mt-2 flex gap-4 text-xs text-[var(--muted-foreground)]">
                <span>Input: ${m.cost_per_1k_input}/1K</span>
                <span>Output: ${m.cost_per_1k_output}/1K</span>
                <span>Cached: ${m.cost_per_1k_cached_input}/1K</span>
                {m.fallback_model_id && <span>Has fallback</span>}
              </div>
            </div>
          ))}
          {models.length === 0 && (
            <p className="text-[var(--muted-foreground)] text-center py-8">
              No models registered. Add LLM models to enable the gateway.
            </p>
          )}
        </div>
      )}

      {/* Routing Rules Tab */}
      {tab === "routing" && (
        <div className="space-y-2">
          {rules.map((r) => (
            <div key={r.id} className="rounded-lg border border-[var(--border)] bg-[var(--card)] p-4">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <span className="rounded bg-zinc-700 px-1.5 py-0.5 text-xs font-mono">
                    P{r.priority}
                  </span>
                  <h3 className="font-medium">{r.name}</h3>
                </div>
                <span className={`rounded-full px-2 py-0.5 text-xs ${r.is_active ? "bg-green-500/20 text-green-400" : "bg-red-500/20 text-red-400"}`}>
                  {r.is_active ? "active" : "disabled"}
                </span>
              </div>
              <div className="mt-2 flex flex-wrap gap-2 text-xs text-[var(--muted-foreground)]">
                {r.match_category && <span>Category: {r.match_category}</span>}
                {r.match_tags?.length > 0 && <span>Tags: {r.match_tags.join(", ")}</span>}
                {r.match_prompt_slugs?.length > 0 && <span>Slugs: {r.match_prompt_slugs.join(", ")}</span>}
              </div>
              {r.description && (
                <p className="mt-1 text-sm text-[var(--muted-foreground)]">{r.description}</p>
              )}
            </div>
          ))}
          {rules.length === 0 && (
            <p className="text-[var(--muted-foreground)] text-center py-8">
              No routing rules configured. The gateway will use default model settings.
            </p>
          )}
        </div>
      )}

      {/* Request Logs Tab */}
      {tab === "logs" && (
        <div className="rounded-lg border border-[var(--border)] overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-[var(--card)] border-b border-[var(--border)] text-left">
                <th className="px-3 py-2 text-xs font-medium text-[var(--muted-foreground)]">Time</th>
                <th className="px-3 py-2 text-xs font-medium text-[var(--muted-foreground)]">Prompt</th>
                <th className="px-3 py-2 text-xs font-medium text-[var(--muted-foreground)]">Model</th>
                <th className="px-3 py-2 text-xs font-medium text-[var(--muted-foreground)]">Tokens</th>
                <th className="px-3 py-2 text-xs font-medium text-[var(--muted-foreground)]">Cost</th>
                <th className="px-3 py-2 text-xs font-medium text-[var(--muted-foreground)]">Latency</th>
                <th className="px-3 py-2 text-xs font-medium text-[var(--muted-foreground)]">Status</th>
              </tr>
            </thead>
            <tbody>
              {logs.map((l) => (
                <tr key={l.id} className="border-b border-[var(--border)] hover:bg-[var(--card)]">
                  <td className="px-3 py-2 text-xs text-[var(--muted-foreground)]">
                    {new Date(l.created_at).toLocaleTimeString()}
                  </td>
                  <td className="px-3 py-2 text-xs font-mono">{l.prompt_slug || "—"}</td>
                  <td className="px-3 py-2 text-xs">{l.model}</td>
                  <td className="px-3 py-2 text-xs text-[var(--muted-foreground)]">
                    {l.input_tokens}↓ {l.output_tokens}↑
                  </td>
                  <td className="px-3 py-2 text-xs">${l.cost_usd.toFixed(4)}</td>
                  <td className="px-3 py-2 text-xs text-[var(--muted-foreground)]">{l.latency_ms}ms</td>
                  <td className="px-3 py-2">
                    <span className={`rounded-full px-2 py-0.5 text-xs ${
                      l.status === "success" ? "bg-green-500/20 text-green-400" :
                      l.status === "error" ? "bg-red-500/20 text-red-400" :
                      "bg-yellow-500/20 text-yellow-400"
                    }`}>
                      {l.status}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {logs.length === 0 && (
            <p className="text-[var(--muted-foreground)] text-center py-8">
              No request logs yet. Logs appear when agents make LLM calls via the gateway.
            </p>
          )}
        </div>
      )}

      {/* Spend Tab */}
      {tab === "spend" && (
        <div className="space-y-3">
          {spend.map((s, i) => (
            <div key={i} className="rounded-lg border border-[var(--border)] bg-[var(--card)] p-4">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <h3 className="font-medium">{s.year_month}</h3>
                  <span className="rounded-full bg-blue-500/20 text-blue-400 px-2 py-0.5 text-xs">
                    {s.provider}
                  </span>
                  <span className="text-xs text-[var(--muted-foreground)]">{s.model}</span>
                </div>
                <span className="text-lg font-bold">${s.total_cost_usd.toFixed(2)}</span>
              </div>
              <div className="mt-2 grid grid-cols-4 gap-4">
                <div>
                  <p className="text-xs text-[var(--muted-foreground)]">Requests</p>
                  <p className="text-sm font-medium">{s.total_requests.toLocaleString()}</p>
                </div>
                <div>
                  <p className="text-xs text-[var(--muted-foreground)]">Input Tokens</p>
                  <p className="text-sm font-medium">{s.total_input_tokens.toLocaleString()}</p>
                </div>
                <div>
                  <p className="text-xs text-[var(--muted-foreground)]">Output Tokens</p>
                  <p className="text-sm font-medium">{s.total_output_tokens.toLocaleString()}</p>
                </div>
                <div>
                  <p className="text-xs text-[var(--muted-foreground)]">Errors</p>
                  <p className="text-sm font-medium">{s.total_errors}</p>
                </div>
              </div>
              {s.budget_limit_usd && (
                <div className="mt-2">
                  <div className="flex justify-between text-xs text-[var(--muted-foreground)]">
                    <span>Budget</span>
                    <span>${s.total_cost_usd.toFixed(2)} / ${s.budget_limit_usd.toFixed(2)}</span>
                  </div>
                  <div className="mt-1 h-1.5 rounded-full bg-[var(--secondary)]">
                    <div
                      className="h-full rounded-full bg-[var(--primary)]"
                      style={{ width: `${Math.min(100, (s.total_cost_usd / s.budget_limit_usd) * 100)}%` }}
                    />
                  </div>
                </div>
              )}
            </div>
          ))}
          {spend.length === 0 && (
            <p className="text-[var(--muted-foreground)] text-center py-8">
              No spend data yet. Spend is tracked when agents make LLM calls via the gateway.
            </p>
          )}
        </div>
      )}
    </div>
  );
}
