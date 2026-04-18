/**
 * ServiceNow REST API client with auth, rate limiting, and retry logic.
 */

export interface SNConfig {
  instanceUrl: string;
  authMethod: "basic" | "oauth2";
  username?: string;
  password?: string;
  accessToken?: string;
}

export interface SNResponse<T = Record<string, unknown>> {
  result: T;
}

export class ServiceNowClient {
  private config: SNConfig;
  private activeRequests = 0;
  private maxConcurrent = 10;

  constructor(config: SNConfig) {
    this.config = {
      ...config,
      instanceUrl: config.instanceUrl.replace(/\/$/, ""),
    };
  }

  static fromEnv(): ServiceNowClient {
    return new ServiceNowClient({
      instanceUrl: process.env.SN_INSTANCE_URL || "",
      authMethod: (process.env.SN_AUTH_METHOD as "basic" | "oauth2") || "basic",
      username: process.env.SN_USERNAME,
      password: process.env.SN_PASSWORD,
      accessToken: process.env.SN_ACCESS_TOKEN,
    });
  }

  private getHeaders(): Record<string, string> {
    const headers: Record<string, string> = {
      Accept: "application/json",
      "Content-Type": "application/json",
    };

    if (this.config.accessToken) {
      headers["Authorization"] = `Bearer ${this.config.accessToken}`;
    }

    return headers;
  }

  private getAuthHeader(): string | undefined {
    if (this.config.username && this.config.password) {
      const encoded = Buffer.from(
        `${this.config.username}:${this.config.password}`
      ).toString("base64");
      return `Basic ${encoded}`;
    }
    return undefined;
  }

  async request<T = Record<string, unknown>>(
    method: string,
    path: string,
    options?: {
      params?: Record<string, string>;
      body?: Record<string, unknown>;
    }
  ): Promise<T> {
    const url = new URL(path, this.config.instanceUrl);
    if (options?.params) {
      for (const [key, value] of Object.entries(options.params)) {
        url.searchParams.set(key, value);
      }
    }

    const headers = this.getHeaders();
    const authHeader = this.getAuthHeader();
    if (authHeader) {
      headers["Authorization"] = authHeader;
    }

    const maxRetries = 3;
    for (let attempt = 0; attempt < maxRetries; attempt++) {
      try {
        const response = await fetch(url.toString(), {
          method,
          headers,
          body: options?.body ? JSON.stringify(options.body) : undefined,
        });

        if (response.status === 429) {
          const wait = Math.min(2 ** attempt * 2, 30) * 1000;
          await new Promise((r) => setTimeout(r, wait));
          continue;
        }

        if (response.status >= 500 && attempt < maxRetries - 1) {
          await new Promise((r) => setTimeout(r, 2 ** attempt * 1000));
          continue;
        }

        if (!response.ok) {
          const text = await response.text();
          throw new Error(
            `ServiceNow API error ${response.status}: ${text.slice(0, 500)}`
          );
        }

        if (response.status === 204) {
          return {} as T;
        }

        return (await response.json()) as T;
      } catch (error) {
        if (
          attempt < maxRetries - 1 &&
          error instanceof TypeError &&
          error.message.includes("fetch")
        ) {
          await new Promise((r) => setTimeout(r, 2 ** attempt * 1000));
          continue;
        }
        throw error;
      }
    }

    throw new Error("Max retries exceeded");
  }

  async getRecord(
    table: string,
    sysId: string,
    fields?: string[]
  ): Promise<Record<string, unknown>> {
    const params: Record<string, string> = {
      sysparm_display_value: "true",
    };
    if (fields) params.sysparm_fields = fields.join(",");

    const result = await this.request<SNResponse>(
      "GET",
      `/api/now/table/${table}/${sysId}`,
      { params }
    );
    return result.result;
  }

  async queryRecords(
    table: string,
    query?: string,
    fields?: string[],
    limit = 100,
    offset = 0
  ): Promise<Record<string, unknown>[]> {
    const params: Record<string, string> = {
      sysparm_limit: String(limit),
      sysparm_offset: String(offset),
      sysparm_display_value: "true",
    };
    if (query) params.sysparm_query = query;
    if (fields) params.sysparm_fields = fields.join(",");

    const result = await this.request<SNResponse<Record<string, unknown>[]>>(
      "GET",
      `/api/now/table/${table}`,
      { params }
    );
    return result.result;
  }

  async createRecord(
    table: string,
    data: Record<string, unknown>
  ): Promise<Record<string, unknown>> {
    const result = await this.request<SNResponse>(
      "POST",
      `/api/now/table/${table}`,
      { body: data }
    );
    return result.result;
  }

  async updateRecord(
    table: string,
    sysId: string,
    data: Record<string, unknown>
  ): Promise<Record<string, unknown>> {
    const result = await this.request<SNResponse>(
      "PATCH",
      `/api/now/table/${table}/${sysId}`,
      { body: data }
    );
    return result.result;
  }

  async deleteRecord(table: string, sysId: string): Promise<void> {
    await this.request("DELETE", `/api/now/table/${table}/${sysId}`);
  }
}
