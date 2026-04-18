"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";

export default function InstancesPage() {
  const [instances, setInstances] = useState<any[]>([]);
  const [showCreate, setShowCreate] = useState(false);
  const [testResult, setTestResult] = useState<Record<string, { success: boolean; message: string }>>({});
  const [form, setForm] = useState({
    name: "",
    instance_url: "",
    auth_method: "basic",
    username: "",
    password: "",
  });

  useEffect(() => {
    api.listInstances().then(setInstances).catch(console.error);
  }, []);

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    const created = await api.createInstance(form);
    setInstances([...instances, created]);
    setShowCreate(false);
    setForm({ name: "", instance_url: "", auth_method: "basic", username: "", password: "" });
  }

  async function handleTest(id: string) {
    setTestResult({ ...testResult, [id]: { success: false, message: "Testing..." } });
    const result = await api.testInstance(id);
    setTestResult({ ...testResult, [id]: result });
    if (result.success) {
      setInstances(
        instances.map((inst) =>
          inst.id === id ? { ...inst, health_status: "healthy", sn_version: result.sn_version } : inst
        )
      );
    }
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold">ServiceNow Instances</h1>
        <button
          onClick={() => setShowCreate(true)}
          className="rounded-lg bg-[var(--primary)] px-4 py-2 text-sm font-medium text-[var(--primary-foreground)]"
        >
          Add Instance
        </button>
      </div>

      {showCreate && (
        <form onSubmit={handleCreate} className="mb-6 rounded-lg border border-[var(--border)] bg-[var(--card)] p-4 space-y-3">
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-sm font-medium mb-1">Name</label>
              <input
                type="text"
                value={form.name}
                onChange={(e) => setForm({ ...form, name: e.target.value })}
                placeholder="Client Dev Instance"
                className="w-full rounded-lg border border-[var(--border)] bg-[var(--background)] px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[var(--ring)]"
                required
              />
            </div>
            <div>
              <label className="block text-sm font-medium mb-1">Instance URL</label>
              <input
                type="url"
                value={form.instance_url}
                onChange={(e) => setForm({ ...form, instance_url: e.target.value })}
                placeholder="https://dev12345.service-now.com"
                className="w-full rounded-lg border border-[var(--border)] bg-[var(--background)] px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[var(--ring)]"
                required
              />
            </div>
            <div>
              <label className="block text-sm font-medium mb-1">Username</label>
              <input
                type="text"
                value={form.username}
                onChange={(e) => setForm({ ...form, username: e.target.value })}
                className="w-full rounded-lg border border-[var(--border)] bg-[var(--background)] px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[var(--ring)]"
                required
              />
            </div>
            <div>
              <label className="block text-sm font-medium mb-1">Password</label>
              <input
                type="password"
                value={form.password}
                onChange={(e) => setForm({ ...form, password: e.target.value })}
                className="w-full rounded-lg border border-[var(--border)] bg-[var(--background)] px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[var(--ring)]"
                required
              />
            </div>
          </div>
          <div className="flex gap-2">
            <button type="submit" className="rounded-lg bg-[var(--primary)] px-4 py-2 text-sm font-medium text-[var(--primary-foreground)]">
              Add Instance
            </button>
            <button type="button" onClick={() => setShowCreate(false)} className="rounded-lg border border-[var(--border)] px-4 py-2 text-sm">
              Cancel
            </button>
          </div>
        </form>
      )}

      <div className="space-y-3">
        {instances.map((inst) => (
          <div key={inst.id} className="rounded-lg border border-[var(--border)] bg-[var(--card)] p-4">
            <div className="flex items-center justify-between">
              <div>
                <h3 className="font-semibold">{inst.name}</h3>
                <p className="text-sm text-[var(--muted-foreground)]">{inst.instance_url}</p>
              </div>
              <div className="flex items-center gap-3">
                <span
                  className={`h-2.5 w-2.5 rounded-full ${
                    inst.health_status === "healthy"
                      ? "bg-green-400"
                      : inst.health_status === "unreachable"
                      ? "bg-red-400"
                      : "bg-yellow-400"
                  }`}
                />
                <span className="text-xs text-[var(--muted-foreground)]">
                  {inst.sn_version || inst.health_status}
                </span>
                <button
                  onClick={() => handleTest(inst.id)}
                  className="rounded-lg border border-[var(--border)] px-3 py-1.5 text-xs hover:bg-[var(--secondary)]"
                >
                  Test Connection
                </button>
              </div>
            </div>
            {testResult[inst.id] && (
              <div
                className={`mt-3 rounded-lg p-2 text-xs ${
                  testResult[inst.id].success
                    ? "bg-green-500/10 text-green-400"
                    : "bg-red-500/10 text-red-400"
                }`}
              >
                {testResult[inst.id].message}
                {testResult[inst.id].success && ` — Version: ${(testResult[inst.id] as any).sn_version}`}
              </div>
            )}
          </div>
        ))}
        {instances.length === 0 && !showCreate && (
          <p className="text-[var(--muted-foreground)] text-center py-12">
            No instances configured. Add your first ServiceNow instance.
          </p>
        )}
      </div>
    </div>
  );
}
