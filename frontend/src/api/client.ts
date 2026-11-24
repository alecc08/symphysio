/* Typed fetch wrapper. Cookies always go along; the CSRF header is added for
   every state-changing call. No token is ever read from or written to storage.
*/

import type {
  AuthResponse,
  ContextDefinition,
  CreatedLog,
  ExerciseDefinition,
  LagResponse,
  Suggestion,
  Summary,
  SymptomDefinition,
  TimeOfDay,
  TimelinePage,
} from "./types";

const BASE = "/api/v1";

export class ApiError extends Error {
  status: number;
  detail: unknown;

  constructor(status: number, detail: unknown) {
    const message =
      typeof detail === "string"
        ? detail
        : Array.isArray(detail)
          ? String(detail[0] ?? "Invalid request")
          : "Request failed";
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
  }
}

export function csrfToken(): string | null {
  const match = document.cookie.match(/(?:^|;\s*)symphysio_csrf=([^;]+)/);
  return match ? decodeURIComponent(match[1]) : null;
}

function parse(text: string): unknown {
  try {
    return JSON.parse(text);
  } catch {
    return text;
  }
}

async function request<T>(
  path: string,
  init: { method?: string; body?: unknown } = {},
): Promise<T> {
  const method = init.method ?? "GET";
  const headers: Record<string, string> = { Accept: "application/json" };
  if (init.body !== undefined) headers["Content-Type"] = "application/json";
  if (method !== "GET" && method !== "HEAD") {
    const token = csrfToken();
    if (token) headers["X-CSRF-Token"] = token;
  }
  const response = await fetch(`${BASE}${path}`, {
    method,
    credentials: "include",
    headers,
    body: init.body === undefined ? undefined : JSON.stringify(init.body),
  });
  if (response.status === 204) return undefined as T;
  const payload = parse(await response.text());
  if (!response.ok) throw new ApiError(response.status, (payload as { detail?: unknown })?.detail ?? payload);
  return payload as T;
}

function qs(params: Record<string, string | number | boolean | undefined>): string {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== "") search.set(key, String(value));
  }
  const query = search.toString();
  return query ? `?${query}` : "";
}

export type CatalogKind = "exercises" | "symptoms" | "contexts";

export const api = {
  register: (email: string, password: string) =>
    request<AuthResponse>("/auth/register", { method: "POST", body: { email, password } }),
  login: (email: string, password: string) =>
    request<AuthResponse>("/auth/login", { method: "POST", body: { email, password } }),
  logout: () => request<void>("/auth/logout", { method: "POST" }),
  logoutAll: () => request<void>("/auth/logout-all", { method: "POST" }),
  me: () => request<AuthResponse>("/auth/me"),
  // The token arrives in a body, not a URL, so it never lands in a proxy access log.
  verifyEmail: (token: string) => request<void>("/auth/verify", { method: "POST", body: { token } }),
  resendVerification: () => request<void>("/auth/verify/resend", { method: "POST", body: {} }),
  // Password reset. The request always answers 202 whether or not the address
  // exists, so the UI must never branch on the status — only on the message.
  requestPasswordReset: (email: string) =>
    request<void>("/auth/password-reset/request", { method: "POST", body: { email } }),
  confirmPasswordReset: (token: string, password: string) =>
    request<void>("/auth/password-reset/confirm", { method: "POST", body: { token, password } }),

  catalog: <T>(kind: CatalogKind, params: Record<string, string | boolean | undefined> = {}) =>
    request<T[]>(`/catalog/${kind}${qs(params)}`),
  suggestions: (kind: CatalogKind) => request<Suggestion[]>(`/catalog/${kind}/suggestions`),
  createExercise: (body: Record<string, unknown>) =>
    request<ExerciseDefinition>("/catalog/exercises", { method: "POST", body }),
  createSymptom: (body: Record<string, unknown>) =>
    request<SymptomDefinition>("/catalog/symptoms", { method: "POST", body }),
  createContext: (body: Record<string, unknown>) =>
    request<ContextDefinition>("/catalog/contexts", { method: "POST", body }),
  patchCatalog: (kind: CatalogKind, id: string, body: Record<string, unknown>) =>
    request<ExerciseDefinition | SymptomDefinition | ContextDefinition>(
      `/catalog/${kind}/${id}`,
      { method: "PATCH", body },
    ),
  reorderCatalog: (kind: CatalogKind, ids: string[]) =>
    request<{ updated: number }>(`/catalog/${kind}/reorder`, { method: "POST", body: { ids } }),

  logExercise: (body: Record<string, unknown>) =>
    request<CreatedLog>("/logs/exercises", { method: "POST", body }),
  logSymptom: (body: Record<string, unknown>) =>
    request<CreatedLog>("/logs/symptoms", { method: "POST", body }),
  logContext: (body: Record<string, unknown>) =>
    request<CreatedLog>("/logs/contexts", { method: "POST", body }),
  patchLog: (type: "exercise" | "symptom" | "context", id: string, body: Record<string, unknown>) =>
    request<unknown>(`/logs/${type}/${id}`, { method: "PATCH", body }),
  deleteLog: (type: "exercise" | "symptom" | "context", id: string) =>
    request<void>(`/logs/${type}/${id}`, { method: "DELETE" }),

  timeline: (params: {
    limit?: number;
    before?: number;
    from?: number;
    to?: number;
    event_type?: string;
  }) => request<TimelinePage>(`/timeline${qs(params)}`),

  summary: (days: number) => request<Summary>(`/analytics/summary${qs({ days })}`),
  lag: (params: { min_hr?: number; max_hr?: number; days?: number; min_count?: number }) =>
    request<LagResponse>(`/analytics/lag-correlations${qs(params)}`),
  timeOfDay: (params: { days?: number; event_type?: string }) =>
    request<TimeOfDay>(`/analytics/time-of-day${qs(params)}`),
};

/** Plain anchors: cookie auth needs no JS, and the browser shows a save dialog. */
export const exportHref = (format: "csv" | "json") => `/api/v1/export/${format}`;
