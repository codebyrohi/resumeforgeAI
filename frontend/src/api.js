// Thin fetch wrapper: base URL from env, JWT in the Authorization header, one silent refresh on 401.
export const API_BASE = (import.meta.env.VITE_API_BASE_URL || "http://localhost:8000").replace(/\/$/, "");

const ACCESS = "rb_access";
const REFRESH = "rb_refresh";

export const tokens = {
  get access() { return localStorage.getItem(ACCESS); },
  get refresh() { return localStorage.getItem(REFRESH); },
  set({ access_token, refresh_token }) {
    localStorage.setItem(ACCESS, access_token);
    localStorage.setItem(REFRESH, refresh_token);
  },
  clear() {
    localStorage.removeItem(ACCESS);
    localStorage.removeItem(REFRESH);
  },
};

export class ApiError extends Error {
  constructor(status, message) {
    super(message);
    this.status = status;
  }
}

async function tryRefresh() {
  if (!tokens.refresh) return false;
  const res = await fetch(`${API_BASE}/auth/refresh`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ refresh_token: tokens.refresh }),
  });
  if (!res.ok) return false;
  tokens.set(await res.json());
  return true;
}

export async function api(path, { method = "GET", json, form, retry = true } = {}) {
  const headers = {};
  if (tokens.access) headers.Authorization = `Bearer ${tokens.access}`;
  let body;
  if (json !== undefined) {
    headers["Content-Type"] = "application/json";
    body = JSON.stringify(json);
  } else if (form) {
    body = form; // browser sets the multipart boundary
  }

  const res = await fetch(`${API_BASE}${path}`, { method, headers, body });
  if (res.status === 401 && retry && (await tryRefresh())) {
    return api(path, { method, json, form, retry: false });
  }
  if (!res.ok) {
    let message = res.statusText;
    try {
      const data = await res.json();
      message = typeof data.detail === "string" ? data.detail
        : Array.isArray(data.detail) ? data.detail.map((d) => d.msg).join("; ") : message;
    } catch { /* non-JSON error body */ }
    if (res.status === 401) tokens.clear();
    throw new ApiError(res.status, message);
  }
  return res.status === 204 ? null : res.json();
}

// Poll a job endpoint until it reaches done/failed.
export async function pollJob(path, { intervalMs = 1500, timeoutMs = 120000 } = {}) {
  const started = Date.now();
  while (Date.now() - started < timeoutMs) {
    const job = await api(path);
    if (job.status === "done" || job.status === "failed") return job;
    await new Promise((r) => setTimeout(r, intervalMs));
  }
  throw new Error("Timed out waiting for the job to finish");
}
