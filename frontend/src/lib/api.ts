const API_BASE = "/api/v1";

class ApiClient {
  private token: string | null = null;

  setToken(token: string) {
    this.token = token;
    if (typeof window !== "undefined") {
      localStorage.setItem("access_token", token);
    }
  }

  getToken(): string | null {
    if (this.token) return this.token;
    if (typeof window !== "undefined") {
      this.token = localStorage.getItem("access_token");
    }
    return this.token;
  }

  clearToken() {
    this.token = null;
    if (typeof window !== "undefined") {
      localStorage.removeItem("access_token");
      localStorage.removeItem("refresh_token");
    }
  }

  private async request<T>(
    path: string,
    options: RequestInit = {}
  ): Promise<T> {
    const token = this.getToken();
    const headers: Record<string, string> = {
      "Content-Type": "application/json",
      ...(options.headers as Record<string, string>),
    };
    if (token) {
      headers["Authorization"] = `Bearer ${token}`;
    }

    const response = await fetch(`${API_BASE}${path}`, {
      ...options,
      headers,
    });

    if (response.status === 401) {
      this.clearToken();
      if (typeof window !== "undefined") {
        window.location.href = "/login";
      }
      throw new Error("Unauthorized");
    }

    if (!response.ok) {
      const error = await response.json().catch(() => ({}));
      throw new Error(error.detail || `API error: ${response.status}`);
    }

    return response.json();
  }

  // Auth
  async register(data: {
    org_name: string;
    email: string;
    password: string;
    full_name: string;
  }) {
    return this.request<{
      access_token: string;
      refresh_token: string;
    }>("/auth/register", { method: "POST", body: JSON.stringify(data) });
  }

  async login(email: string, password: string) {
    return this.request<{
      access_token: string;
      refresh_token: string;
    }>("/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    });
  }

  async getMe() {
    return this.request<{
      id: string;
      email: string;
      full_name: string;
      organization_id: string;
      is_org_admin: boolean;
    }>("/auth/me");
  }

  // Projects
  async listProjects() {
    return this.request<any[]>("/projects");
  }

  async createProject(data: { name: string; description?: string; instance_id?: string }) {
    return this.request<any>("/projects", { method: "POST", body: JSON.stringify(data) });
  }

  async getProject(id: string) {
    return this.request<any>(`/projects/${id}`);
  }

  // Instances
  async listInstances() {
    return this.request<any[]>("/instances");
  }

  async createInstance(data: {
    name: string;
    instance_url: string;
    auth_method: string;
    username?: string;
    password?: string;
  }) {
    return this.request<any>("/instances", { method: "POST", body: JSON.stringify(data) });
  }

  async testInstance(id: string) {
    return this.request<{ success: boolean; sn_version?: string; message: string }>(
      `/instances/${id}/test`,
      { method: "POST" }
    );
  }

  // Stories
  async listStories(projectId: string) {
    return this.request<any[]>(`/projects/${projectId}/stories`);
  }

  async createStory(projectId: string, data: { title: string; description?: string; acceptance_criteria?: string }) {
    return this.request<any>(`/projects/${projectId}/stories`, {
      method: "POST",
      body: JSON.stringify(data),
    });
  }

  // Jobs
  async listJobs(projectId: string) {
    return this.request<any[]>(`/projects/${projectId}/jobs`);
  }

  async createJob(projectId: string, data: { agent_id: string; story_id?: string; instance_id: string }) {
    return this.request<any>(`/projects/${projectId}/jobs`, {
      method: "POST",
      body: JSON.stringify(data),
    });
  }

  async getJob(projectId: string, jobId: string) {
    return this.request<any>(`/projects/${projectId}/jobs/${jobId}`);
  }

  async approveJob(projectId: string, jobId: string) {
    return this.request<any>(`/projects/${projectId}/jobs/${jobId}/approve`, { method: "POST" });
  }

  // Artifacts
  async listArtifacts(projectId: string, jobId?: string) {
    const params = jobId ? `?job_id=${jobId}` : "";
    return this.request<any[]>(`/projects/${projectId}/artifacts${params}`);
  }

  // Connectors
  async listConnectors() {
    return this.request<any[]>("/connectors");
  }

  async createConnector(data: {
    platform: string;
    label: string;
    description?: string;
    connector_type?: string;
    base_url?: string;
    config?: any;
  }) {
    return this.request<any>("/connectors", { method: "POST", body: JSON.stringify(data) });
  }

  async getConnector(id: string) {
    return this.request<any>(`/connectors/${id}`);
  }

  async updateConnector(id: string, data: any) {
    return this.request<any>(`/connectors/${id}`, { method: "PUT", body: JSON.stringify(data) });
  }

  async deleteConnector(id: string) {
    return this.request<any>(`/connectors/${id}`, { method: "DELETE" });
  }

  async saveConnectorCredentials(id: string, credentials: Record<string, string>) {
    return this.request<any>(`/connectors/${id}/credentials`, {
      method: "POST",
      body: JSON.stringify({ credentials }),
    });
  }

  async getConnectorCredentials(id: string) {
    return this.request<any>(`/connectors/${id}/credentials`);
  }

  async verifyConnector(id: string) {
    return this.request<any>(`/connectors/${id}/verify`, { method: "POST" });
  }

  async listConnectorActions(connectorId: string) {
    return this.request<any[]>(`/connectors/${connectorId}/actions`);
  }

  // Story Attachments
  async uploadAttachment(projectId: string, storyId: string, file: File, caption?: string) {
    const formData = new FormData();
    formData.append("file", file);
    if (caption) formData.append("caption", caption);

    const token = this.getToken();
    const response = await fetch(`${API_BASE}/projects/${projectId}/stories/${storyId}/attachments`, {
      method: "POST",
      headers: { Authorization: `Bearer ${token}` },
      body: formData,
    });
    if (!response.ok) {
      const error = await response.json().catch(() => ({}));
      throw new Error(error.detail || `Upload failed: ${response.status}`);
    }
    return response.json();
  }

  async listAttachments(projectId: string, storyId: string) {
    return this.request<any[]>(`/projects/${projectId}/stories/${storyId}/attachments`);
  }

  async deleteAttachment(projectId: string, storyId: string, attachmentId: string) {
    return this.request<any>(`/projects/${projectId}/stories/${storyId}/attachments/${attachmentId}`, {
      method: "DELETE",
    });
  }

  // Epic Execution Plan
  async getEpicExecutionPlan(projectId: string, epicId: string) {
    return this.request<any>(`/projects/${projectId}/stories/epic/${epicId}/execution-plan`);
  }

  // Figma Import
  async importFigmaStories(projectId: string, data: {
    figma_url: string;
    connector_id: string;
    portal_type?: string;
  }) {
    return this.request<any>(`/projects/${projectId}/stories/import-figma`, {
      method: "POST",
      body: JSON.stringify(data),
    });
  }

  async createProjectFromFigma(data: {
    figma_url: string;
    connector_id: string;
    project_name?: string;
    instance_id?: string;
    portal_type?: string;
  }) {
    return this.request<any>("/projects/from-figma", {
      method: "POST",
      body: JSON.stringify(data),
    });
  }

  // AI Control Plane — Models & Logs
  async listModelConfigs() {
    return this.request<any[]>("/control-plane/models");
  }

  async listRequestLogs(params?: { limit?: number; prompt_slug?: string }) {
    const qs = params ? "?" + new URLSearchParams(params as any).toString() : "";
    return this.request<any[]>(`/control-plane/logs${qs}`);
  }

  async listMonthlySpend() {
    return this.request<any[]>("/control-plane/spend");
  }
}

export const api = new ApiClient();
