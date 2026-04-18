"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";

interface ApiKey {
  id: string;
  provider: string;
  label: string;
  key_preview: string;
  is_active: boolean;
  notes: string | null;
}

export default function SettingsPage() {
  const [keys, setKeys] = useState<ApiKey[]>([]);
  const [showAdd, setShowAdd] = useState(false);
  const [newKey, setNewKey] = useState({
    provider: "anthropic",
    label: "Default",
    api_key: "",
    notes: "",
  });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  useEffect(() => {
    loadKeys();
  }, []);

  async function loadKeys() {
    try {
      const token = api.getToken();
      const res = await fetch("/api/v1/settings/api-keys", {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.status === 401) {
        window.location.href = "/login";
        return;
      }
      if (res.ok) setKeys(await res.json());
    } catch (err) {
      console.error("Failed to load keys:", err);
    }
  }

  async function handleAdd(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    setError("");
    setSuccess("");
    try {
      const token = api.getToken();
      const res = await fetch("/api/v1/settings/api-keys", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify(newKey),
      });
      if (!res.ok) {
        const data = await res.json();
        throw new Error(data.detail || "Failed to save");
      }
      setSuccess("API key saved securely.");
      setShowAdd(false);
      setNewKey({ provider: "anthropic", label: "Default", api_key: "", notes: "" });
      loadKeys();
    } catch (err: any) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  }

  async function handleToggle(key: ApiKey) {
    const token = api.getToken();
    await fetch(`/api/v1/settings/api-keys/${key.id}`, {
      method: "PATCH",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify({ is_active: !key.is_active }),
    });
    loadKeys();
  }

  async function handleDelete(key: ApiKey) {
    if (!confirm(`Delete "${key.label}" (${key.key_preview})?`)) return;
    const token = api.getToken();
    await fetch(`/api/v1/settings/api-keys/${key.id}`, {
      method: "DELETE",
      headers: { Authorization: `Bearer ${token}` },
    });
    loadKeys();
  }

  const providerInfo: Record<string, { name: string; color: string; placeholder: string }> = {
    anthropic: {
      name: "Anthropic (Claude)",
      color: "text-orange-400",
      placeholder: "sk-ant-api03-...",
    },
    openai: {
      name: "OpenAI",
      color: "text-green-400",
      placeholder: "sk-proj-...",
    },
  };

  return (
    <div className="max-w-2xl">
      <div className="mb-6">
        <h1 className="text-2xl font-bold">Settings</h1>
        <p className="text-sm text-[var(--muted-foreground)] mt-1">
          Manage API keys and organization configuration
        </p>
      </div>

      {/* API Keys Section */}
      <div className="rounded-lg border border-[var(--border)] bg-[var(--card)] p-5">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h2 className="text-lg font-semibold">LLM API Keys</h2>
            <p className="text-xs text-[var(--muted-foreground)] mt-0.5">
              Keys are encrypted at rest and never exposed in API responses
            </p>
          </div>
          <button
            onClick={() => setShowAdd(true)}
            className="rounded-lg bg-[var(--primary)] px-3 py-1.5 text-xs font-medium text-[var(--primary-foreground)] hover:opacity-90"
          >
            + Add Key
          </button>
        </div>

        {success && (
          <div className="mb-4 rounded-lg bg-green-500/10 border border-green-500/20 p-3 text-sm text-green-400">
            {success}
          </div>
        )}

        {/* Add Key Form */}
        {showAdd && (
          <form onSubmit={handleAdd} className="mb-4 rounded-lg border border-[var(--border)] bg-[var(--background)] p-4 space-y-3">
            {error && (
              <div className="rounded-lg bg-red-500/10 border border-red-500/20 p-2 text-xs text-red-400">
                {error}
              </div>
            )}
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-xs font-medium mb-1">Provider</label>
                <select
                  value={newKey.provider}
                  onChange={(e) => setNewKey({ ...newKey, provider: e.target.value })}
                  className="w-full rounded-lg border border-[var(--border)] bg-[var(--card)] px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[var(--ring)]"
                >
                  <option value="anthropic">Anthropic (Claude)</option>
                  <option value="openai">OpenAI</option>
                </select>
              </div>
              <div>
                <label className="block text-xs font-medium mb-1">Label</label>
                <input
                  type="text"
                  value={newKey.label}
                  onChange={(e) => setNewKey({ ...newKey, label: e.target.value })}
                  placeholder="e.g., Production Key"
                  className="w-full rounded-lg border border-[var(--border)] bg-[var(--card)] px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[var(--ring)]"
                />
              </div>
            </div>
            <div>
              <label className="block text-xs font-medium mb-1">API Key</label>
              <input
                type="password"
                value={newKey.api_key}
                onChange={(e) => setNewKey({ ...newKey, api_key: e.target.value })}
                placeholder={providerInfo[newKey.provider]?.placeholder || "Enter API key..."}
                className="w-full rounded-lg border border-[var(--border)] bg-[var(--card)] px-3 py-2 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-[var(--ring)]"
                required
              />
            </div>
            <div className="flex gap-2">
              <button
                type="submit"
                disabled={saving}
                className="rounded-lg bg-[var(--primary)] px-4 py-2 text-sm font-medium text-[var(--primary-foreground)] disabled:opacity-50"
              >
                {saving ? "Encrypting..." : "Save Key"}
              </button>
              <button
                type="button"
                onClick={() => { setShowAdd(false); setError(""); }}
                className="rounded-lg border border-[var(--border)] px-4 py-2 text-sm"
              >
                Cancel
              </button>
            </div>
          </form>
        )}

        {/* Key List */}
        <div className="space-y-2">
          {keys.map((key) => (
            <div
              key={key.id}
              className="flex items-center justify-between rounded-lg border border-[var(--border)] bg-[var(--background)] p-3"
            >
              <div className="flex items-center gap-3">
                <div
                  className={`h-2 w-2 rounded-full ${key.is_active ? "bg-green-400" : "bg-zinc-500"}`}
                />
                <div>
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-medium">{key.label}</span>
                    <span className={`text-xs ${providerInfo[key.provider]?.color || ""}`}>
                      {providerInfo[key.provider]?.name || key.provider}
                    </span>
                  </div>
                  <span className="text-xs text-[var(--muted-foreground)] font-mono">
                    {key.key_preview}
                  </span>
                </div>
              </div>
              <div className="flex items-center gap-2">
                <button
                  onClick={() => handleToggle(key)}
                  className="rounded-lg border border-[var(--border)] px-2 py-1 text-xs hover:bg-[var(--secondary)]"
                >
                  {key.is_active ? "Disable" : "Enable"}
                </button>
                <button
                  onClick={() => handleDelete(key)}
                  className="rounded-lg border border-red-500/30 px-2 py-1 text-xs text-red-400 hover:bg-red-500/10"
                >
                  Delete
                </button>
              </div>
            </div>
          ))}
          {keys.length === 0 && !showAdd && (
            <p className="text-sm text-[var(--muted-foreground)] text-center py-6">
              No API keys configured. Add your Anthropic key to start using AI agents.
            </p>
          )}
        </div>
      </div>
    </div>
  );
}
