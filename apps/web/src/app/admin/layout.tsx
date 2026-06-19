"use client";

import type { ReactNode } from "react";
import "../globals.css";
import "../room-layout.css";

export default function AdminLayout({ children }: { children: ReactNode }) {
  return (
    <>
      <div style={{
        display: "flex", justifyContent: "space-between", alignItems: "center",
        padding: "12px 24px", borderBottom: "1px solid var(--border)",
        background: "var(--bg-raised)", position: "sticky", top: 0, zIndex: 50,
      }}>
        <span style={{ fontWeight: 700, fontSize: "15px", color: "var(--text)" }}>
          CoC Yes <span style={{ color: "var(--text-muted)", fontWeight: 400 }}>Admin</span>
        </span>
        <a href="/" style={{ fontSize: "13px", color: "var(--text-secondary)", textDecoration: "none" }}>
          返回前台
        </a>
      </div>
      {children}
    </>
  );
}
