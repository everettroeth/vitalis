import type {
  User,
  Account,
  UserPreferences,
  ConnectedDevice,
  WearableDaily,
  SleepSession,
  WearableActivity,
  BloodPanel,
  BloodMarker,
  BiomarkerDictionary,
  Supplement,
  SupplementLog,
  MoodJournal,
  Measurement,
  CustomMetric,
  CustomMetricEntry,
  Goal,
  GoalAlert,
  Document as VitalisDocument,
  ApiError,
} from "@/types";

// ── Configuration ──

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const API_V1 = `${API_BASE}/api/v1`;

// ── Error Handling ──

export class VitalisApiError extends Error {
  constructor(
    public status: number,
    public detail: string,
  ) {
    super(detail);
    this.name = "VitalisApiError";
  }
}

// ── Typed Fetch Wrapper ──

async function request<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const url = path.startsWith("http") ? path : `${API_V1}${path}`;

  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options.headers as Record<string, string>),
  };

  // TODO: Inject Clerk session token when auth is integrated
  // const token = await getToken();
  // if (token) headers["Authorization"] = `Bearer ${token}`;

  const res = await fetch(url, {
    ...options,
    headers,
  });

  if (!res.ok) {
    let detail = "An unexpected error occurred";
    try {
      const err: ApiError = await res.json();
      detail = err.detail;
    } catch {
      detail = res.statusText;
    }
    throw new VitalisApiError(res.status, detail);
  }

  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

function get<T>(path: string) {
  return request<T>(path, { method: "GET" });
}

function post<T>(path: string, body?: unknown) {
  return request<T>(path, {
    method: "POST",
    body: body ? JSON.stringify(body) : undefined,
  });
}

function patch<T>(path: string, body: unknown) {
  return request<T>(path, {
    method: "PATCH",
    body: JSON.stringify(body),
  });
}

function del(path: string) {
  return request<void>(path, { method: "DELETE" });
}

// ── API Client ──

export const api = {
  // ── Health ──
  health: () => request<{ status: string }>(`${API_BASE}/health`),

  // ── Users ──
  users: {
    me: () => get<User>("/users/me"),
    updateMe: (data: Partial<User>) => patch<User>("/users/me", data),
    account: () => get<Account>("/users/me/account"),
    updateAccount: (data: Partial<Account>) => patch<Account>("/users/me/account", data),
    preferences: () => get<UserPreferences>("/users/me/preferences"),
    updatePreferences: (data: Partial<UserPreferences>) =>
      patch<UserPreferences>("/users/me/preferences", data),
  },

  // ── Wearables ──
  wearables: {
    devices: () => get<ConnectedDevice[]>("/wearables/devices"),
    addDevice: (data: Partial<ConnectedDevice>) =>
      post<ConnectedDevice>("/wearables/devices", data),
    updateDevice: (id: string, data: Partial<ConnectedDevice>) =>
      patch<ConnectedDevice>(`/wearables/devices/${id}`, data),
    removeDevice: (id: string) => del(`/wearables/devices/${id}`),

    daily: (params?: { start_date?: string; end_date?: string; source?: string; limit?: number }) => {
      const qs = new URLSearchParams();
      if (params?.start_date) qs.set("start_date", params.start_date);
      if (params?.end_date) qs.set("end_date", params.end_date);
      if (params?.source) qs.set("source", params.source);
      if (params?.limit) qs.set("limit", String(params.limit));
      return get<WearableDaily[]>(`/wearables/daily?${qs}`);
    },
    addDaily: (data: Partial<WearableDaily>) => post<WearableDaily>("/wearables/daily", data),
    getDaily: (id: string) => get<WearableDaily>(`/wearables/daily/${id}`),

    sleep: (params?: { start_date?: string; end_date?: string; limit?: number }) => {
      const qs = new URLSearchParams();
      if (params?.start_date) qs.set("start_date", params.start_date);
      if (params?.end_date) qs.set("end_date", params.end_date);
      if (params?.limit) qs.set("limit", String(params.limit));
      return get<SleepSession[]>(`/wearables/sleep?${qs}`);
    },
    addSleep: (data: Partial<SleepSession>) => post<SleepSession>("/wearables/sleep", data),

    activities: (params?: { start_date?: string; end_date?: string; activity_type?: string; limit?: number }) => {
      const qs = new URLSearchParams();
      if (params?.start_date) qs.set("start_date", params.start_date);
      if (params?.end_date) qs.set("end_date", params.end_date);
      if (params?.activity_type) qs.set("activity_type", params.activity_type);
      if (params?.limit) qs.set("limit", String(params.limit));
      return get<WearableActivity[]>(`/wearables/activities?${qs}`);
    },
    addActivity: (data: Partial<WearableActivity>) =>
      post<WearableActivity>("/wearables/activities", data),
  },

  // ── Blood Work ──
  bloodWork: {
    panels: (params?: { limit?: number }) => {
      const qs = params?.limit ? `?limit=${params.limit}` : "";
      return get<BloodPanel[]>(`/blood-work/panels${qs}`);
    },
    addPanel: (data: Partial<BloodPanel>) => post<BloodPanel>("/blood-work/panels", data),
    getPanel: (id: string) => get<BloodPanel>(`/blood-work/panels/${id}`),
    updatePanel: (id: string, data: Partial<BloodPanel>) =>
      patch<BloodPanel>(`/blood-work/panels/${id}`, data),
    deletePanel: (id: string) => del(`/blood-work/panels/${id}`),

    panelMarkers: (panelId: string) =>
      get<BloodMarker[]>(`/blood-work/panels/${panelId}/markers`),
    addMarker: (data: Partial<BloodMarker>) => post<BloodMarker>("/blood-work/markers", data),
    updateMarker: (id: string, data: Partial<BloodMarker>) =>
      patch<BloodMarker>(`/blood-work/markers/${id}`, data),
    markerTrend: (biomarkerId: string, params?: { limit?: number }) => {
      const qs = params?.limit ? `?limit=${params.limit}` : "";
      return get<BloodMarker[]>(`/blood-work/markers/trend/${biomarkerId}${qs}`);
    },

    biomarkers: (params?: { category?: string; search?: string; limit?: number }) => {
      const qs = new URLSearchParams();
      if (params?.category) qs.set("category", params.category);
      if (params?.search) qs.set("search", params.search);
      if (params?.limit) qs.set("limit", String(params.limit));
      return get<BiomarkerDictionary[]>(`/blood-work/biomarkers?${qs}`);
    },
  },

  // ── Supplements ──
  supplements: {
    list: (activeOnly = true) =>
      get<Supplement[]>(`/supplements?active_only=${activeOnly}`),
    add: (data: Partial<Supplement>) => post<Supplement>("/supplements", data),
    get: (id: string) => get<Supplement>(`/supplements/${id}`),
    update: (id: string, data: Partial<Supplement>) =>
      patch<Supplement>(`/supplements/${id}`, data),
    remove: (id: string) => del(`/supplements/${id}`),

    addLog: (supplementId: string, data: Partial<SupplementLog>) =>
      post<SupplementLog>(`/supplements/${supplementId}/logs`, data),
    logs: (supplementId: string, params?: { limit?: number }) => {
      const qs = params?.limit ? `?limit=${params.limit}` : "";
      return get<SupplementLog[]>(`/supplements/${supplementId}/logs${qs}`);
    },
  },

  // ── Mood Journal ──
  moodJournal: {
    list: (params?: { start_date?: string; end_date?: string; limit?: number }) => {
      const qs = new URLSearchParams();
      if (params?.start_date) qs.set("start_date", params.start_date);
      if (params?.end_date) qs.set("end_date", params.end_date);
      if (params?.limit) qs.set("limit", String(params.limit));
      return get<MoodJournal[]>(`/mood-journal?${qs}`);
    },
    add: (data: Partial<MoodJournal>) => post<MoodJournal>("/mood-journal", data),
    get: (id: string) => get<MoodJournal>(`/mood-journal/${id}`),
    update: (id: string, data: Partial<MoodJournal>) =>
      patch<MoodJournal>(`/mood-journal/${id}`, data),
    remove: (id: string) => del(`/mood-journal/${id}`),
  },

  // ── Goals ──
  goals: {
    list: (activeOnly = true) =>
      get<Goal[]>(`/goals?active_only=${activeOnly}`),
    add: (data: Partial<Goal>) => post<Goal>("/goals", data),
    get: (id: string) => get<Goal>(`/goals/${id}`),
    update: (id: string, data: Partial<Goal>) => patch<Goal>(`/goals/${id}`, data),
    remove: (id: string) => del(`/goals/${id}`),

    alerts: (goalId: string, params?: { limit?: number }) => {
      const qs = params?.limit ? `?limit=${params.limit}` : "";
      return get<GoalAlert[]>(`/goals/${goalId}/alerts${qs}`);
    },
    acknowledgeAlert: (goalId: string, alertId: string) =>
      post<GoalAlert>(`/goals/${goalId}/alerts/${alertId}/acknowledge`),
  },

  // ── Measurements ──
  measurements: {
    list: (params?: { metric?: string; limit?: number }) => {
      const qs = new URLSearchParams();
      if (params?.metric) qs.set("metric", params.metric);
      if (params?.limit) qs.set("limit", String(params.limit));
      return get<Measurement[]>(`/measurements?${qs}`);
    },
    add: (data: Partial<Measurement>) => post<Measurement>("/measurements", data),
    get: (id: string) => get<Measurement>(`/measurements/${id}`),
    update: (id: string, data: Partial<Measurement>) =>
      patch<Measurement>(`/measurements/${id}`, data),
    remove: (id: string) => del(`/measurements/${id}`),

    customMetrics: () => get<CustomMetric[]>("/measurements/custom"),
    addCustomMetric: (data: Partial<CustomMetric>) =>
      post<CustomMetric>("/measurements/custom", data),
    addCustomEntry: (metricId: string, data: Partial<CustomMetricEntry>) =>
      post<CustomMetricEntry>(`/measurements/custom/${metricId}/entries`, data),
    customEntries: (metricId: string, params?: { limit?: number }) => {
      const qs = params?.limit ? `?limit=${params.limit}` : "";
      return get<CustomMetricEntry[]>(`/measurements/custom/${metricId}/entries${qs}`);
    },
  },

  // ── Documents ──
  documents: {
    list: (params?: { document_type?: string; limit?: number }) => {
      const qs = new URLSearchParams();
      if (params?.document_type) qs.set("document_type", params.document_type);
      if (params?.limit) qs.set("limit", String(params.limit));
      return get<VitalisDocument[]>(`/documents?${qs}`);
    },
    get: (id: string) => get<VitalisDocument>(`/documents/${id}`),
    downloadUrl: (id: string) =>
      get<{ url: string; expires_in: number }>(`/documents/${id}/download-url`),
    update: (id: string, data: Partial<VitalisDocument>) =>
      patch<VitalisDocument>(`/documents/${id}`, data),
    remove: (id: string) => del(`/documents/${id}`),

    upload: async (file: File, documentType: string, providerName?: string) => {
      const formData = new FormData();
      formData.append("file", file);
      formData.append("document_type", documentType);
      if (providerName) formData.append("provider_name", providerName);

      const res = await fetch(`${API_V1}/documents/upload`, {
        method: "POST",
        body: formData,
        // Don't set Content-Type — browser handles multipart boundary
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: res.statusText }));
        throw new VitalisApiError(res.status, err.detail);
      }
      return res.json() as Promise<VitalisDocument>;
    },
  },
};
