"use client";

import { useEffect, useState } from "react";
import { API_BASE_URL } from "@/lib/api";

type HealthPayload = {
  status: string;
  service: string;
  version: string;
};

type RequestState =
  | { kind: "loading" }
  | { kind: "ready"; data: HealthPayload }
  | { kind: "error"; message: string };

export function ApiStatus() {
  const [state, setState] = useState<RequestState>({ kind: "loading" });

  useEffect(() => {
    let active = true;

    async function load() {
      try {
        const response = await fetch(`${API_BASE_URL}/api/health`);

        if (!response.ok) {
          throw new Error(`HTTP ${response.status}`);
        }

        const data = (await response.json()) as HealthPayload;

        if (active) {
          setState({ kind: "ready", data });
        }
      } catch (error) {
        const message = error instanceof Error ? error.message : "Unknown error";

        if (active) {
          setState({ kind: "error", message });
        }
      }
    }

    load();

    return () => {
      active = false;
    };
  }, []);

  return (
    <article className="panel panel--accent">
      <p className="panel__kicker">API Health</p>
      <h2>后端连通状态</h2>
      {state.kind === "loading" ? (
        <p className="status status--loading">正在连接 FastAPI 服务...</p>
      ) : null}
      {state.kind === "ready" ? (
        <div className="status status--ready">
          <span>在线</span>
          <strong>{state.data.service}</strong>
          <small>v{state.data.version}</small>
        </div>
      ) : null}
      {state.kind === "error" ? (
        <p className="status status--error">
          未连接：{state.message}。请确认后端正在运行在 {API_BASE_URL}。
        </p>
      ) : null}
    </article>
  );
}
