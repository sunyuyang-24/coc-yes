export const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || "";

export function apiUrl(path: string) {
  return `${API_BASE_URL}${path}`;
}

export function wsUrl(path: string) {
  const base = new URL(API_BASE_URL);
  base.protocol = base.protocol === "https:" ? "wss:" : "ws:";
  // 分离 path 中内嵌的查询参数，避免 search="" 清掉
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

export async function apiRequest<T>(path: string, init?: RequestInit): Promise<T> {
  const headers = new Headers(init?.headers);
  headers.set("Content-Type", "application/json");

  const response = await fetch(apiUrl(path), {
    ...init,
    headers
  });

  if (!response.ok) {
    const errorText = await response.text();
    throw new Error(errorText || `HTTP ${response.status}`);
  }

  return response.json() as Promise<T>;
}
