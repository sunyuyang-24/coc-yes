"use client";

import { Component } from "react";

interface Props { children: React.ReactNode; }
interface State { hasError: boolean; error: Error | null; }

export class ErrorBoundary extends Component<Props, State> {
  state: State = { hasError: false, error: null };

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  render() {
    if (this.state.hasError) {
      return (
        <div style={{
          display: "flex", flexDirection: "column", alignItems: "center",
          justifyContent: "center", height: "100%", padding: "32px",
          color: "var(--text-secondary)", gap: "16px"
        }}>
          <p style={{ fontSize: "18px", color: "var(--error)" }}>页面加载出错</p>
          <p style={{ fontSize: "13px" }}>{this.state.error?.message || "未知错误"}</p>
          <button className="button button--primary"
            onClick={() => { this.setState({ hasError: false, error: null }); window.location.reload(); }}>
            重新加载
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}
