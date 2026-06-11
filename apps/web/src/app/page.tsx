import { ApiStatus } from "@/components/api-status";
import { SettingsPanel } from "@/components/settings-panel";
import { RoomConsole } from "@/components/room-console";

export default function Home() {
  return (
    <main className="shell">
      <header className="topbar">
        <span className="topbar__brand">COC Yes</span>
        <nav className="topbar__nav">
          <a href="#rooms">房间</a>
          <a href="#settings">设置</a>
        </nav>
      </header>

      <section id="rooms">
        <RoomConsole />
      </section>

      <section id="settings">
        <SettingsPanel />
      </section>

      <footer className="footer">
        <ApiStatus />
      </footer>
    </main>
  );
}