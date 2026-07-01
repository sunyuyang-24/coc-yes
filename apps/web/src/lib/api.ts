export const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || "";

export function apiUrl(path: string) {
  const base = API_BASE_URL.replace(/\/+$/, "");
  return `${base}${path}`;
}

export function wsUrl(path: string) {
  // Handle empty/relative API_BASE_URL — derive from current page origin
  const origin = API_BASE_URL || (typeof window !== "undefined" ? window.location.origin : "http://localhost:3002");
  const base = new URL(origin);
  base.protocol = base.protocol === "https:" ? "wss:" : "ws:";
  const qIndex = path.indexOf("?");
  if (qIndex >= 0) {
    base.pathname = path.slice(0, qIndex);
    base.search = path.slice(qIndex);
  } else {
    base.pathname = path;
    base.search = "";
  }
  base.hash = "";
  return base.toString();
}

import { getToken } from "./auth";

export async function apiRequest<T>(path: string, init?: RequestInit): Promise<T> {
  const headers = new Headers(init?.headers);
  const method = (init?.method || "GET").toUpperCase();
  if (!headers.has("Content-Type") && method !== "GET" && method !== "HEAD" && !(init?.body instanceof FormData)) {
    headers.set("Content-Type", "application/json");
  }

  const token = getToken();
  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }

  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 15000);
  try {
    const response = await fetch(apiUrl(path), {
      ...init,
      headers,
      signal: controller.signal,
    });

    if (!response.ok) {
      const errorText = await response.text();
      let message = errorText || `HTTP ${response.status}`;
      try {
        const json = JSON.parse(errorText);
        if (typeof json.detail === "string") {
          message = json.detail;
        } else if (json.message) {
          message = json.message;
        }
      } catch {
        // 不是 JSON，保留原始文本
      }
      const err = Object.assign(new Error(message), { status: response.status });
      throw err;
    }

    return response.json() as Promise<T>;
  } finally {
    clearTimeout(timeoutId);
  }
}
