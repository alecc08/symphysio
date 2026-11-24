/* Typed fetch wrapper. Cookies always go along; the CSRF header is added for
   every state-changing call. No token is ever read from or written to storage.
*/

import type {
  Associations,
  AuthResponse,
  ContextDefinition,
  CreatedLog,
  ExerciseDefinition,
  PlanEvent,
  Preferences,
  Profile,
  Suggestion,
  Summary,
  SymptomDefinition,
  SymptomTrend,
  TimeOfDay,
  TimelinePage,
} from "./types";

import { browserLocale, storedLocale } from "../i18n/resolve";

const BASE = "/api/v1";

/** The device's IANA zone, sent so an unauthenticated request can be answered in
 *  the right shape. Never stored without the person choosing it: a laptop in the
 *  wrong zone should not pin a wrong zone to an account forever. */
export function deviceTimezone(): string {
  try {
    return Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC";
  } catch {
    return "UTC";
  }
}

// Set by the i18n provider. One place owns the language; the headers below read
// it, so the sign-up mail, a failed login and a validation error all come back in
// the language the person is looking at — including before there is an account.
// It starts from the device's own choice rather than from English, because the
// very first request (the sign-up profile list, the confirm-mail language) is
// answered before React has run an effect.
let language: string = storedLocale() ?? browserLocale();

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
  const headers: Record<string, string> = {
    Accept: "application/json",
    // The server writes its own words — a failed login, a validation error, the
    // sign-up confirmation mail — and this is the only signal it has before the
    // person has an account to hold a preference.
    "Accept-Language": language === "fr" ? "fr-CA,fr;q=0.9" : "en-CA,en;q=0.9",
    "X-Timezone": deviceTimezone(),
  };
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
  /** The i18n provider calls this on every change; the headers above read it. */
  setLocale: (next: string) => {
    language = next === "fr" ? "fr" : "en";
  },
  register: (email: string, password: string, profile?: string, locale?: string) =>
    request<AuthResponse>("/auth/register", {
      method: "POST",
      // Sent explicitly when the caller chooses: an omitted profile means "the old
      // default" to the API, which is not the same answer as "start empty". The
      // language is sent explicitly too, because it decides what the account is
      // *seeded with* — French preset names become rows — and that question can
      // only be asked once.
      body: {
        email,
        password,
        ...(profile === undefined ? {} : { profile }),
        ...(locale === undefined ? {} : { locale }),
      },
    }),
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
  // "What follows X?" The window label must be one the account's profile offers;
  // the server rejects invented ones, so the UI only ever sends these.
  associations: (params: { days?: number; window?: string; exposure?: string }) =>
    request<Associations>(`/analytics/associations${qs(params)}`),
  symptomTrend: (definitionId: string, params: { days?: number; baseline_days?: number }) =>
    request<SymptomTrend>(`/analytics/symptoms/${definitionId}${qs(params)}`),
  timeOfDay: (params: { days?: number; event_type?: string }) =>
    request<TimeOfDay>(`/analytics/time-of-day${qs(params)}`),

  profiles: () => request<Profile[]>("/catalog/profiles"),
  // The two account preferences. `effective_timezone` is what the server is
  // actually cutting days with, which is not always the stored one: an account
  // that never chose inherits the instance default, and Settings has to say so.
  preferences: () => request<Preferences>("/auth/preferences"),
  patchPreferences: (body: { locale?: string; timezone?: string | null }) =>
    request<Preferences>("/auth/preferences", { method: "PATCH", body }),
  // Plan events: the appointment layer. Read and written by the signed-in person.
  planEvents: (params: { limit?: number; from?: number; to?: number } = {}) =>
    request<PlanEvent[]>(`/plan-events${qs(params)}`),
  createPlanEvent: (body: Record<string, unknown>) =>
    request<PlanEvent>("/plan-events", { method: "POST", body }),
  patchPlanEvent: (id: string, body: Record<string, unknown>) =>
    request<PlanEvent>(`/plan-events/${id}`, { method: "PATCH", body }),
  deletePlanEvent: (id: string) => request<void>(`/plan-events/${id}`, { method: "DELETE" }),
};

/** Plain anchors: cookie auth needs no JS, and the browser shows a save dialog. */
export const exportHref = (format: "csv" | "json") => `/api/v1/export/${format}`;
