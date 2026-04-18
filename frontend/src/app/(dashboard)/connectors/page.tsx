"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";

const PLATFORM_PRESETS: Record<string, { label: string; connector_type: string; base_url: string; config: any; description: string }> = {
  anthropic: {
    label: "Anthropic",
    connector_type: "api_key",
    base_url: "https://api.anthropic.com",
    description: "Claude AI models for agent reasoning and code generation",
    config: {
      required_keys: [{ key: "api_key", label: "API Key", type: "secret", required: true }],
      setup_instructions: "1. Go to console.anthropic.com\n2. Navigate to Settings → API Keys\n3. Click 'Create Key'\n4. Copy the key and paste it below",
    },
  },
  openai: {
    label: "OpenAI",
    connector_type: "api_key",
    base_url: "https://api.openai.com",
    description: "GPT models and embeddings for AI-powered features",
    config: {
      required_keys: [{ key: "api_key", label: "API Key", type: "secret", required: true }],
      setup_instructions: "1. Go to platform.openai.com\n2. Navigate to API Keys\n3. Click 'Create new secret key'\n4. Copy the key and paste it below",
    },
  },
  servicenow: {
    label: "ServiceNow",
    connector_type: "basic_auth",
    base_url: "",
    description: "ServiceNow instance for deploying portals, catalog items, and scripts",
    config: {
      required_keys: [
        { key: "instance_url", label: "Instance URL", type: "text", required: true },
        { key: "username", label: "Username", type: "text", required: true },
        { key: "password", label: "Password", type: "secret", required: true },
      ],
      setup_instructions: "1. Enter your instance URL (e.g., https://dev12345.service-now.com)\n2. Use an admin account with 'admin' and 'sp_admin' roles\n3. For PDIs: default admin password is in your instance request email\n4. Ensure REST API access is enabled on the instance",
    },
  },
  figma: {
    label: "Figma",
    connector_type: "bearer_token",
    base_url: "https://api.figma.com",
    description: "Import designs from Figma to auto-generate portal stories",
    config: {
      required_keys: [{ key: "access_token", label: "Personal Access Token", type: "secret", required: true }],
      setup_instructions: "1. Go to figma.com and log in\n2. Click your profile icon → Settings\n3. Scroll to 'Personal access tokens'\n4. Click 'Generate new token'\n5. Give it a description and copy the token",
    },
  },
  slack: {
    label: "Slack",
    connector_type: "bearer_token",
    base_url: "https://slack.com/api",
    description: "Send notifications and updates to Slack channels",
    config: {
      required_keys: [{ key: "bot_token", label: "Bot Token", type: "secret", required: true }],
      setup_instructions: "1. Go to api.slack.com/apps\n2. Click 'Create New App' → 'From scratch'\n3. Add OAuth scopes: chat:write, channels:read\n4. Install to your workspace\n5. Copy the 'Bot User OAuth Token' (starts with xoxb-)",
    },
  },
  github: {
    label: "GitHub",
    connector_type: "bearer_token",
    base_url: "https://api.github.com",
    description: "Access repositories and manage code artifacts",
    config: {
      required_keys: [{ key: "personal_access_token", label: "Personal Access Token", type: "secret", required: true }],
      setup_instructions: "1. Go to github.com → Settings\n2. Navigate to Developer Settings → Personal Access Tokens → Fine-grained tokens\n3. Click 'Generate new token'\n4. Select repository access and permissions\n5. Copy the token",
    },
  },
};

const statusColors: Record<string, string> = {
  connected: "bg-green-500",
  disconnected: "bg-yellow-500",
  error: "bg-red-500",
};

export default function ConnectorsPage() {
  const router = useRouter();
  const [connectors, setConnectors] = useState<any[]>([]);
  const [showCreate, setShowCreate] = useState(false);
  const [selectedPlatform, setSelectedPlatform] = useState("");

  useEffect(() => {
    api.listConnectors().then(setConnectors).catch(console.error);
  }, []);

  const handleCreate = async () => {
    if (!selectedPlatform) return;
    const preset = PLATFORM_PRESETS[selectedPlatform];
    if (!preset) return;

    try {
      const connector = await api.createConnector({
        platform: selectedPlatform,
        label: preset.label,
        description: preset.description,
        connector_type: preset.connector_type,
        base_url: preset.base_url,
        config: preset.config,
      });
      // Redirect to detail page to set up credentials
      router.push(`/connectors/${connector.id}`);
    } catch (e: any) {
      alert(e.message);
    }
  };

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold">Connectors</h1>
          <p className="text-sm text-[var(--muted-foreground)] mt-1">
            Manage integrations with external systems
          </p>
        </div>
        <button
          onClick={() => setShowCreate(!showCreate)}
          className="rounded-lg bg-[var(--primary)] px-4 py-2 text-sm font-medium text-[var(--primary-foreground)]"
        >
          {showCreate ? "Cancel" : "Add Connector"}
        </button>
      </div>

      {showCreate && (
        <div className="mb-6 rounded-lg border border-[var(--border)] bg-[var(--card)] p-4">
          <h3 className="text-sm font-medium mb-3">Select Platform</h3>
          <div className="grid grid-cols-3 gap-2 mb-4">
            {Object.entries(PLATFORM_PRESETS).map(([key, preset]) => (
              <button
                key={key}
                onClick={() => setSelectedPlatform(key)}
                className={`rounded-lg border px-3 py-2 text-sm text-left transition-colors ${
                  selectedPlatform === key
                    ? "border-[var(--primary)] bg-[var(--primary)]/10 text-[var(--primary)]"
                    : "border-[var(--border)] hover:border-[var(--muted-foreground)]"
                }`}
              >
                {preset.label}
              </button>
            ))}
          </div>
          {selectedPlatform && (
            <button
              onClick={handleCreate}
              className="rounded-lg bg-[var(--primary)] px-4 py-2 text-sm font-medium text-[var(--primary-foreground)]"
            >
              Create {PLATFORM_PRESETS[selectedPlatform]?.label} Connector
            </button>
          )}
        </div>
      )}

      <div className="space-y-3">
        {connectors.length === 0 && (
          <p className="text-sm text-[var(--muted-foreground)]">
            No connectors configured. Add one to integrate with external systems.
          </p>
        )}
        {connectors.map((c) => (
          <Link
            key={c.id}
            href={`/connectors/${c.id}`}
            className="block rounded-lg border border-[var(--border)] bg-[var(--card)] p-4 hover:border-[var(--primary)]/50 transition-colors"
          >
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className={`h-2.5 w-2.5 rounded-full ${statusColors[c.status] || "bg-gray-500"}`} />
                <div>
                  <div className="flex items-center gap-2">
                    <h3 className="font-medium">{c.label}</h3>
                    {c.instance_label && (
                      <span className="rounded bg-[var(--secondary)] px-1.5 py-0.5 text-xs text-[var(--muted-foreground)]">
                        {c.instance_label}
                      </span>
                    )}
                  </div>
                  <p className="text-xs text-[var(--muted-foreground)]">
                    {c.platform} &middot; {c.connector_type} &middot; {c.status}
                  </p>
                </div>
              </div>
              <div className="flex items-center gap-2">
                {c.has_credentials && (
                  <span className="rounded-full bg-green-500/10 text-green-400 px-2 py-0.5 text-xs">
                    credentials set
                  </span>
                )}
                <span className="text-xs text-[var(--muted-foreground)]">→</span>
              </div>
            </div>
          </Link>
        ))}
      </div>
    </div>
  );
}
