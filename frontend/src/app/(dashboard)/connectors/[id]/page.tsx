"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import { api } from "@/lib/api";

const statusColors: Record<string, string> = {
  connected: "bg-green-500/20 text-green-400",
  disconnected: "bg-yellow-500/20 text-yellow-400",
  error: "bg-red-500/20 text-red-400",
};

export default function ConnectorDetailPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const [connector, setConnector] = useState<any>(null);
  const [credInputs, setCredInputs] = useState<Record<string, string>>({});
  const [savedCreds, setSavedCreds] = useState<Record<string, string>>({});
  const [verifyResult, setVerifyResult] = useState<any>(null);
  const [saving, setSaving] = useState(false);
  const [verifying, setVerifying] = useState(false);
  const [message, setMessage] = useState("");
  const [actions, setActions] = useState<any[]>([]);
  const [editing, setEditing] = useState(false);
  const [editLabel, setEditLabel] = useState("");
  const [editInstanceLabel, setEditInstanceLabel] = useState("");

  useEffect(() => {
    if (!id) return;
    api.getConnector(id).then((c) => {
      setConnector(c);
      setEditLabel(c.label);
      setEditInstanceLabel(c.instance_label || "");
    });
    api.getConnectorCredentials(id).then(setSavedCreds).catch(() => {});
    api.listConnectorActions(id).then(setActions).catch(() => {});
  }, [id]);

  const handleSaveCreds = async () => {
    if (!id) return;
    setSaving(true);
    setMessage("");
    try {
      await api.saveConnectorCredentials(id, credInputs);
      setCredInputs({});
      const updated = await api.getConnector(id);
      setConnector(updated);
      const creds = await api.getConnectorCredentials(id);
      setSavedCreds(creds);
      setMessage("Credentials saved successfully");
    } catch (e: any) {
      setMessage(`Error: ${e.message}`);
    }
    setSaving(false);
  };

  const handleVerify = async () => {
    if (!id) return;
    setVerifying(true);
    setVerifyResult(null);
    try {
      const result = await api.verifyConnector(id);
      setVerifyResult(result);
      const updated = await api.getConnector(id);
      setConnector(updated);
    } catch (e: any) {
      setVerifyResult({ status: "error", message: e.message });
    }
    setVerifying(false);
  };

  const handleDelete = async () => {
    if (!confirm("Delete this connector? This cannot be undone.")) return;
    try {
      await api.deleteConnector(id!);
      router.push("/connectors");
    } catch (e: any) {
      setMessage(`Error: ${e.message}`);
    }
  };

  const handleUpdateLabel = async () => {
    if (!id) return;
    try {
      await api.updateConnector(id, { label: editLabel, instance_label: editInstanceLabel || null });
      const updated = await api.getConnector(id);
      setConnector(updated);
      setEditing(false);
    } catch (e: any) {
      setMessage(`Error: ${e.message}`);
    }
  };

  if (!connector) return <div className="text-[var(--muted-foreground)]">Loading...</div>;

  const requiredKeys = connector.config?.required_keys || [];
  const setupInstructions = connector.config?.setup_instructions || "";

  return (
    <div className="max-w-3xl">
      {/* Back link */}
      <Link href="/connectors" className="text-xs text-[var(--muted-foreground)] hover:text-[var(--foreground)] mb-4 inline-block">
        ← Back to Connectors
      </Link>

      {/* Header */}
      <div className="flex items-start justify-between mb-6">
        <div>
          {editing ? (
            <div className="space-y-2">
              <input
                value={editLabel}
                onChange={(e) => setEditLabel(e.target.value)}
                className="text-xl font-bold bg-transparent border-b border-[var(--border)] focus:outline-none focus:border-[var(--primary)]"
              />
              <input
                value={editInstanceLabel}
                onChange={(e) => setEditInstanceLabel(e.target.value)}
                placeholder="Instance label (e.g., Dev, Prod)"
                className="block text-sm bg-transparent border-b border-[var(--border)] focus:outline-none focus:border-[var(--primary)]"
              />
              <div className="flex gap-2">
                <button onClick={handleUpdateLabel} className="rounded bg-[var(--primary)] px-3 py-1 text-xs text-[var(--primary-foreground)]">Save</button>
                <button onClick={() => setEditing(false)} className="rounded border border-[var(--border)] px-3 py-1 text-xs">Cancel</button>
              </div>
            </div>
          ) : (
            <>
              <div className="flex items-center gap-3">
                <h1 className="text-2xl font-bold">{connector.label}</h1>
                {connector.instance_label && (
                  <span className="rounded bg-[var(--secondary)] px-2 py-0.5 text-xs">{connector.instance_label}</span>
                )}
                <span className={`rounded-full px-2 py-0.5 text-xs ${statusColors[connector.status] || "bg-gray-500/20"}`}>
                  {connector.status}
                </span>
              </div>
              <p className="text-sm text-[var(--muted-foreground)] mt-1">
                {connector.platform} &middot; {connector.connector_type}
                {connector.base_url && ` &middot; ${connector.base_url}`}
              </p>
            </>
          )}
        </div>
        <div className="flex gap-2">
          {!editing && (
            <button onClick={() => setEditing(true)} className="rounded border border-[var(--border)] px-3 py-1.5 text-xs hover:bg-[var(--secondary)]">
              Edit
            </button>
          )}
          <button onClick={handleDelete} className="rounded border border-red-500/30 px-3 py-1.5 text-xs text-red-400 hover:bg-red-500/10">
            Delete
          </button>
        </div>
      </div>

      {message && (
        <div className={`mb-4 rounded-lg p-3 text-sm ${message.startsWith("Error") ? "bg-red-500/10 text-red-400" : "bg-green-500/10 text-green-400"}`}>
          {message}
        </div>
      )}

      {/* Setup Instructions */}
      {setupInstructions && (
        <div className="mb-6 rounded-lg border border-[var(--border)] bg-[var(--card)] p-4">
          <h2 className="text-sm font-bold mb-2">Setup Instructions</h2>
          <div className="text-sm text-[var(--muted-foreground)] whitespace-pre-line">
            {setupInstructions}
          </div>
        </div>
      )}

      {/* Saved Credentials */}
      {Object.keys(savedCreds).length > 0 && (
        <div className="mb-6 rounded-lg border border-[var(--border)] bg-[var(--card)] p-4">
          <h2 className="text-sm font-bold mb-2">Saved Credentials</h2>
          <div className="space-y-1">
            {Object.entries(savedCreds).map(([key, value]) => (
              <div key={key} className="flex items-center justify-between text-sm">
                <span className="text-[var(--muted-foreground)]">{key}</span>
                <span className="font-mono text-xs text-[var(--muted-foreground)]">{value as string}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Credential Form */}
      <div className="mb-6 rounded-lg border border-[var(--border)] bg-[var(--card)] p-4">
        <h2 className="text-sm font-bold mb-3">
          {Object.keys(savedCreds).length > 0 ? "Update Credentials" : "Add Credentials"}
        </h2>
        <div className="space-y-3">
          {requiredKeys.map((key: any) => (
            <div key={key.key}>
              <label className="text-xs font-medium text-[var(--muted-foreground)]">
                {key.label}
                {key.required && <span className="text-red-400 ml-0.5">*</span>}
              </label>
              <input
                type={key.type === "secret" ? "password" : "text"}
                placeholder={key.label}
                value={credInputs[key.key] || ""}
                onChange={(e) => setCredInputs((p) => ({ ...p, [key.key]: e.target.value }))}
                className="mt-1 w-full rounded-lg border border-[var(--border)] bg-[var(--background)] px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[var(--ring)]"
              />
            </div>
          ))}
        </div>
        <div className="mt-4 flex items-center gap-3">
          <button
            onClick={handleSaveCreds}
            disabled={saving || Object.values(credInputs).every((v) => !v)}
            className="rounded-lg bg-[var(--primary)] px-4 py-2 text-sm font-medium text-[var(--primary-foreground)] disabled:opacity-40"
          >
            {saving ? "Saving..." : "Save Credentials"}
          </button>
          <button
            onClick={handleVerify}
            disabled={verifying || !connector.has_credentials}
            className="rounded-lg border border-[var(--border)] px-4 py-2 text-sm hover:bg-[var(--secondary)] disabled:opacity-40"
          >
            {verifying ? "Testing..." : "Test Connection"}
          </button>
        </div>
      </div>

      {/* Verify Result */}
      {verifyResult && (
        <div className={`mb-6 rounded-lg p-4 text-sm ${
          verifyResult.status === "connected" ? "bg-green-500/10 text-green-400 border border-green-500/20" : "bg-red-500/10 text-red-400 border border-red-500/20"
        }`}>
          <p className="font-medium">{verifyResult.status === "connected" ? "Connection Successful" : "Connection Failed"}</p>
          <p className="text-xs mt-1 opacity-80">{verifyResult.message}</p>
        </div>
      )}

      {/* Last verified */}
      {connector.last_verified_at && (
        <p className="text-xs text-[var(--muted-foreground)] mb-6">
          Last verified: {new Date(connector.last_verified_at).toLocaleString()}
        </p>
      )}

      {/* Actions */}
      {actions.length > 0 && (
        <div className="rounded-lg border border-[var(--border)] bg-[var(--card)] p-4">
          <h2 className="text-sm font-bold mb-3">Available Actions</h2>
          <div className="space-y-2">
            {actions.map((a) => (
              <div key={a.id} className="flex items-center justify-between rounded border border-[var(--border)] px-3 py-2">
                <div>
                  <span className="text-sm font-medium">{a.label}</span>
                  <span className="ml-2 rounded bg-blue-500/20 text-blue-400 px-1.5 py-0.5 text-xs">
                    {a.method}
                  </span>
                  <p className="text-xs text-[var(--muted-foreground)] mt-0.5">{a.endpoint_path}</p>
                </div>
                {a.category && (
                  <span className="text-xs text-[var(--muted-foreground)]">{a.category}</span>
                )}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
