"use client";

import { useState } from "react";
import type { FormEvent } from "react";
import { login, register } from "@/lib/auth";

export function LoginPanel({ onAuth }: { onAuth: () => void }) {
  const [mode, setMode] = useState<"login" | "register">("login");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      if (mode === "register") {
        await register(username, password, displayName || username);
      } else {
        await login(username, password);
      }
      onAuth();
    } catch (err) {
      setError(err instanceof Error ? err.message : "认证失败");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div style={{
      display: "flex", alignItems: "center", justifyContent: "center",
      minHeight: "100vh", background: "var(--bg)",
    }}>
      <form onSubmit={handleSubmit} style={{
        width: "100%", maxWidth: "380px", padding: "32px",
        background: "var(--bg-raised)", borderRadius: "12px",
        border: "1px solid var(--border)", display: "flex", flexDirection: "column", gap: "16px",
      }}>
        <h1 style={{ fontSize: "22px", textAlign: "center", margin: "0 0 8px 0", color: "var(--text)" }}>
          CoC Yes
        </h1>

        <div style={{ display: "flex", borderRadius: "8px", overflow: "hidden", border: "1px solid var(--border)" }}>
          <button type="button" onClick={() => setMode("login")} style={{
            flex: 1, padding: "8px", border: "none", cursor: "pointer", fontSize: "14px",
            background: mode === "login" ? "var(--accent)" : "var(--bg-hover)",
            color: mode === "login" ? "#fff" : "var(--text-muted)",
            transition: "background 0.15s",
          }}>
            登录
          </button>
          <button type="button" onClick={() => setMode("register")} style={{
            flex: 1, padding: "8px", border: "none", cursor: "pointer", fontSize: "14px",
            background: mode === "register" ? "var(--accent)" : "var(--bg-hover)",
            color: mode === "register" ? "#fff" : "var(--text-muted)",
            transition: "background 0.15s",
          }}>
            注册
          </button>
        </div>

        <label style={{ display: "flex", flexDirection: "column", gap: "4px", fontSize: "13px", color: "var(--text-muted)" }}>
          用户名
          <input value={username} onChange={(e) => setUsername(e.target.value)} required
            minLength={2} maxLength={32} autoComplete="username"
            style={{
              padding: "10px 12px", borderRadius: "8px", border: "1px solid var(--border)",
              background: "var(--bg-hover)", color: "var(--text)", fontSize: "15px", outline: "none",
            }} />
        </label>

        <label style={{ display: "flex", flexDirection: "column", gap: "4px", fontSize: "13px", color: "var(--text-muted)" }}>
          密码
          <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} required
            minLength={4} maxLength={128} autoComplete={mode === "register" ? "new-password" : "current-password"}
            style={{
              padding: "10px 12px", borderRadius: "8px", border: "1px solid var(--border)",
              background: "var(--bg-hover)", color: "var(--text)", fontSize: "15px", outline: "none",
            }} />
        </label>

        {mode === "register" && (
          <label style={{ display: "flex", flexDirection: "column", gap: "4px", fontSize: "13px", color: "var(--text-muted)" }}>
            显示名称
            <input value={displayName} onChange={(e) => setDisplayName(e.target.value)}
              minLength={1} maxLength={64} placeholder="可选，默认与用户名相同"
              style={{
                padding: "10px 12px", borderRadius: "8px", border: "1px solid var(--border)",
                background: "var(--bg-hover)", color: "var(--text)", fontSize: "15px", outline: "none",
              }} />
          </label>
        )}

        {error && (
          <p style={{ color: "var(--danger)", fontSize: "13px", margin: 0, textAlign: "center" }}>{error}</p>
        )}

        <button type="submit" disabled={loading} style={{
          padding: "10px", borderRadius: "8px", border: "none", cursor: loading ? "not-allowed" : "pointer",
          background: "var(--accent)", color: "#fff", fontSize: "15px", fontWeight: 600,
          opacity: loading ? 0.7 : 1,
        }}>
          {loading ? "处理中..." : mode === "register" ? "注册并登录" : "登录"}
        </button>
      </form>
    </div>
  );
}
