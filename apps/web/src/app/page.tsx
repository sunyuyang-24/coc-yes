import { ApiStatus } from "@/components/api-status";
import { SettingsPanel } from "@/components/settings-panel";
import { RoomConsole } from "@/components/room-console";
import { BUILD_PHASES, CORE_MODULES } from "@coc-yes/shared";

export default function Home() {
  return (
    <main className="shell">
      <section className="hero">
        <div className="hero__copy">
          <p className="eyebrow">COC Yes · Keeper Workspace</p>
          <h1>让调查员从 Excel 里走上桌面。</h1>
          <p className="hero__lead">
            阶段 3 正在接入角色卡上传与解析。玩家上传 Excel 后，房间会展示属性、技能和背景摘要。
          </p>
          <div className="hero__actions">
            <a href="#status" className="button button--primary">
              检查服务状态
            </a>
            <a href="#roadmap" className="button button--ghost">
              查看阶段路线
            </a>
            <a href="#rooms" className="button button--ghost">
              打开房间面板
            </a>
          </div>
        </div>

        <div className="table-card" aria-label="项目模块状态">
          <div className="table-card__header">
            <span>Character Desk</span>
            <strong>阶段 3</strong>
          </div>
          <div className="table-card__grid">
            {CORE_MODULES.map((module) => (
              <div className="module-chip" key={module.key}>
                <span>{module.label}</span>
                <small>{module.stage}</small>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section id="rooms">
        <RoomConsole />
      </section>

      <section className="status-grid" id="status">
        <ApiStatus />
        <SettingsPanel />
        <article className="panel">
          <p className="panel__kicker">Project Shape</p>
          <h2>前后端已经分层</h2>
          <p>
            前端负责跑团工作台体验，后端负责可信骰子、角色卡解析、规则检索、录音和总结入口。
          </p>
        </article>
        <article className="panel">
          <p className="panel__kicker">Source Safety</p>
          <h2>本地资料不会提交</h2>
          <p>
            规则书 PDF、上传文件和索引都被排除在 Git 外，后续只在私有运行环境中使用。
          </p>
        </article>
      </section>

      <section className="roadmap" id="roadmap">
        <div>
          <p className="eyebrow">Roadmap</p>
          <h2>一步一步跑通，最后补全完整需求。</h2>
        </div>
        <ol className="phase-list">
          {BUILD_PHASES.map((phase) => (
            <li key={phase.key}>
              <span>{phase.order.toString().padStart(2, "0")}</span>
              <div>
                <strong>{phase.label}</strong>
                <p>{phase.goal}</p>
              </div>
            </li>
          ))}
        </ol>
      </section>
    </main>
  );
}
