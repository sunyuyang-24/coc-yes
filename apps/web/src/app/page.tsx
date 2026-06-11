import { ApiStatus } from "@/components/api-status";
import { SettingsPanel } from "@/components/settings-panel";
import { RoomConsole } from "@/components/room-console";

export default function Home() {
  return (
    <main className="shell">
      {/* ── Top bar ── */}
      <header className="topbar">
        <div className="topbar__brand">
          <span className="topbar__logo">&#x2B21;</span>
          <span className="topbar__title">CoC Yes</span>
          <span className="topbar__divider" />
          <span className="topbar__subtitle">克苏鲁的呼唤跑团助手</span>
        </div>
        <nav className="topbar__nav">
          <ApiStatus />
        </nav>
      </header>

      {/* ── Main content ── */}
      <div className="layout">
        <aside className="sidebar">
          <SettingsPanel />
        </aside>

        <section className="main-area" id="rooms">
          <RoomConsole />
        </section>
      </div>
    </main>
  );
}
