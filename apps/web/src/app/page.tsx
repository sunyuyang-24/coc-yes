import { ApiStatus } from "@/components/api-status";
import { ErrorBoundary } from "@/components/error-boundary";
import { RoomConsole } from "@/components/room-console";

export default function Home() {
  return (
    <main className="shell">
      <header className="topbar">
        <div className="topbar__brand">
          <span className="topbar__logo">&#x2B21;</span>
          <span className="topbar__title">CoC Yes</span>
        </div>
        <nav className="topbar__nav">
          <ApiStatus />
        </nav>
      </header>
      <div style={{ flex: 1, display: "flex", flexDirection: "column", overflow: "hidden" }}>
        <ErrorBoundary>
          <RoomConsole />
        </ErrorBoundary>
      </div>
    </main>
  );
}