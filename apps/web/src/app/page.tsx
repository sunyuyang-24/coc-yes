import { ApiStatus } from "@/components/api-status";
import { ErrorBoundary } from "@/components/error-boundary";
import { RoomConsole } from "@/components/room-console";
import { CustomBackgroundLayer } from "@/components/settings-panel";

export default function Home() {
  return (
    <main className="shell">
      <CustomBackgroundLayer />
      <header className="topbar" style={{ position: "relative", zIndex: 2 }}>
        <div className="topbar__brand">
          <span className="topbar__logo">&#x2B21;</span>
          <span className="topbar__title">CoC Yes</span>
        </div>
        <nav className="topbar__nav">
          <ApiStatus />
        </nav>
      </header>
      <div style={{ flex: 1, display: "flex", flexDirection: "column", overflow: "hidden", position: "relative", zIndex: 1 }}>
        <ErrorBoundary>
          <RoomConsole />
        </ErrorBoundary>
      </div>
    </main>
  );
}