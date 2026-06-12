// ── API client for the Loom v2 REST API ──────────────────────────────────

const BASE_URL = import.meta.env.VITE_API_BASE_URL || "/api/v2";

function getToken(): string | null {
  return localStorage.getItem("loom_token");
}

function authHeaders(): Record<string, string> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
  };
  const token = getToken();
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }
  return headers;
}

async function request<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const url = `${BASE_URL}${path}`;
  const res = await fetch(url, {
    ...options,
    headers: {
      ...authHeaders(),
      ...(options.headers as Record<string, string> | undefined),
    },
  });

  if (res.status === 401) {
    localStorage.removeItem("loom_token");
    if (window.location.pathname !== "/login") {
      window.location.href = "/login";
    }
    throw new Error("Unauthorized");
  }

  if (!res.ok) {
    const body = await res.text();
    let detail = body;
    try {
      const parsed = JSON.parse(body);
      detail = parsed.detail || body;
    } catch {
      /* not JSON */
    }
    throw new Error(detail || `Request failed with status ${res.status}`);
  }

  if (res.status === 204) return undefined as T;
  return res.json();
}

// ── Types ──────────────────────────────────────────────────────────────────

export interface Observation {
  id: string;
  observation_type: string;
  domain: string;
  category: string;
  content: string;
  confidence: number;
  times_confirmed: number;
  times_violated: number;
  source_urls: string[];
  source_agent: string;
  source_session: string;
  tags: string[];
  access_scope: string;
  created_at: string;
  updated_at: string;
  context?: Record<string, unknown> | null;
}

export interface ObservationCreate {
  domain?: string;
  category?: string;
  content: string;
  observation_type?: string;
  confidence?: number;
  source_url?: string;
  source_agent?: string;
  source_session?: string;
  tags?: string[];
  access_scope?: string;
  context?: Record<string, unknown> | null;
}

export interface SearchRequest {
  query?: string;
  domain?: string | null;
  observation_type?: string | null;
  tags?: string[] | null;
  min_confidence?: number;
  limit?: number;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
  org_id: string;
  user_id: string;
}

export interface UserResponse {
  user_id: string;
  org_id: string;
  scope: string;
}

export interface OrgResponse {
  id: string;
  name: string;
  slug: string;
  role: string;
  created_at: string;
}

export interface MemberResponse {
  id: string;
  email: string;
  oauth_provider: string;
  role: string;
}

export interface GraphLink {
  source: string;
  target: string;
  relation: string;
}

export interface RelatedResponse {
  id: string;
  related: string[];
  depth: number;
  links: GraphLink[];
}

export interface Stats {
  total_observations?: number;
  by_domain?: Record<string, number>;
  by_type?: Record<string, number>;
  by_confidence?: Record<string, number>;
  [key: string]: unknown;
}

export interface AuditEntry {
  id?: string;
  timestamp: string;
  action_type: string;
  agent: string;
  details: string;
  observation_id?: string | null;
  domain?: string | null;
  user_id?: string | null;
}

// ── Observations ───────────────────────────────────────────────────────────

export function getObservations(params?: {
  domain?: string;
  type?: string;
  tags?: string;
  min_confidence?: number;
  limit?: number;
  offset?: number;
}): Promise<Observation[]> {
  const searchParams = new URLSearchParams();
  if (params?.domain) searchParams.set("domain", params.domain);
  if (params?.type) searchParams.set("type", params.type);
  if (params?.tags) searchParams.set("tags", params.tags);
  if (params?.min_confidence) searchParams.set("min_confidence", String(params.min_confidence));
  if (params?.limit) searchParams.set("limit", String(params.limit));
  if (params?.offset) searchParams.set("offset", String(params.offset));
  const qs = searchParams.toString();
  return request<Observation[]>(`/observations${qs ? `?${qs}` : ""}`);
}

export function getObservation(id: string): Promise<Observation> {
  return request<Observation>(`/observations/${encodeURIComponent(id)}`);
}

export function createObservation(data: ObservationCreate): Promise<Observation> {
  return request<Observation>("/observations", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export function updateObservation(
  id: string,
  data: Partial<ObservationCreate>,
): Promise<Observation> {
  return request<Observation>(`/observations/${encodeURIComponent(id)}`, {
    method: "PATCH",
    body: JSON.stringify(data),
  });
}

export function deleteObservation(id: string): Promise<{ deleted: boolean; id: string }> {
  return request(`/observations/${encodeURIComponent(id)}`, {
    method: "DELETE",
  });
}

export function searchObservations(data: SearchRequest): Promise<Observation[]> {
  return request<Observation[]>("/search", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

// ── Stats ──────────────────────────────────────────────────────────────────

export function getStats(domain?: string): Promise<Stats> {
  const qs = domain ? `?domain=${encodeURIComponent(domain)}` : "";
  return request<Stats>(`/stats${qs}`);
}

// ── Graph ──────────────────────────────────────────────────────────────────

export function getRelated(
  obsId: string,
  depth: number = 1,
): Promise<RelatedResponse> {
  return request<RelatedResponse>(
    `/graph/related/${encodeURIComponent(obsId)}?depth=${depth}`,
  );
}

export function addGraphLink(
  sourceId: string,
  targetId: string,
  relationType: string = "related_to",
): Promise<{ source: string; target: string; relation: string }> {
  return request("/graph/links", {
    method: "POST",
    body: JSON.stringify({
      source_id: sourceId,
      target_id: targetId,
      relation_type: relationType,
    }),
  });
}

// ── Auth ───────────────────────────────────────────────────────────────────

export function getMe(): Promise<UserResponse> {
  return request<UserResponse>("/auth/me");
}

export function refreshToken(): Promise<TokenResponse> {
  return request<TokenResponse>("/auth/refresh", { method: "POST" });
}

// ── Orgs ───────────────────────────────────────────────────────────────────

export function getOrgs(): Promise<OrgResponse[]> {
  return request<OrgResponse[]>("/orgs");
}

export function getOrgMembers(orgId: string): Promise<MemberResponse[]> {
  return request<MemberResponse[]>(`/orgs/${encodeURIComponent(orgId)}/members`);
}

// ── Audit ──────────────────────────────────────────────────────────────────

export function getAuditLog(params?: {
  action_type?: string;
  limit?: number;
  offset?: number;
}): Promise<AuditEntry[]> {
  const searchParams = new URLSearchParams();
  if (params?.action_type) searchParams.set("action_type", params.action_type);
  if (params?.limit) searchParams.set("limit", String(params.limit));
  if (params?.offset) searchParams.set("offset", String(params.offset));
  const qs = searchParams.toString();
  return request<AuditEntry[]>(`/audit${qs ? `?${qs}` : ""}`);
}

// ── Utility ────────────────────────────────────────────────────────────────

export function storeToken(token: string): void {
  localStorage.setItem("loom_token", token);
}

export function clearToken(): void {
  localStorage.removeItem("loom_token");
}

export function isAuthenticated(): boolean {
  return !!getToken();
}
