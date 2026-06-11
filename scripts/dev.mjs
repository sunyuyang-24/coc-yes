import { spawn } from "node:child_process";
import { existsSync } from "node:fs";
import { join } from "node:path";

const ROOT = process.cwd();
const npm = process.platform === "win32" ? "npm.cmd" : "npm";
const node = process.execPath;

// ── 日志工具 ──
const tag = (name, color) => {
  const codes = { api: "\x1b[36m", web: "\x1b[33m", system: "\x1b[35m" };
  const c = codes[name] ?? codes.system;
  return `${c}[${name}]\x1b[0m`;
};

const log = (name, msg) => console.log(`${tag(name)} ${msg}`);

// ── API 启动逻辑 ──
const apiDir = join(ROOT, "apps", "api");
const venvPython = process.platform === "win32"
  ? join(apiDir, ".venv", "Scripts", "python.exe")
  : join(apiDir, ".venv", "bin", "python");

const python = process.env.PYTHON || (existsSync(venvPython) ? venvPython : "python");

// ── 启动子进程（失败自动重试一次） ──
function startProcess(name, command, args, cwd, useShell = false) {
  log(name, "正在启动...");

  const child = spawn(command, args, {
    cwd: cwd ?? ROOT,
    stdio: "pipe",
    shell: useShell,
  });

  child.stdout.on("data", (d) => process.stdout.write(`${tag(name)} ${d}`));
  child.stderr.on("data", (d) => process.stderr.write(`${tag(name)} ${d}`));

  child.on("error", (err) => {
    log(name, `启动失败: ${err.message}`);
    if (name === "api") {
      log("system", "提示: 后端需要 Python 3.10+ 和 uvicorn。");
      log("system", "手动启动: cd apps\\api && .venv\\Scripts\\python -m uvicorn app.main:app --reload");
    }
  });

  let crashed = false;
  child.on("exit", (code, signal) => {
    if (!crashed && code && code !== 0) {
      crashed = true;
      log(name, `异常退出 (code ${code})，3秒后自动重启...`);
      setTimeout(() => startProcess(name, command, args, cwd), 3000);
    } else if (signal) {
      log(name, `被信号终止 (${signal})`);
    } else {
      log(name, `已退出 (code ${code ?? 0})`);
    }
  });

  return child;
}

// ── 启动 ──
log("system", "═══════════════════════════════════════");
log("system", "CoC Yes - 在线跑团助手");
log("system", `后端 API:  http://127.0.0.1:${process.env.API_PORT || "8000"}`);
log("system", `前端页面:  http://localhost:3002`);
log("system", "按 Ctrl+C 停止所有服务");
log("system", "═══════════════════════════════════════");

const children = [
  startProcess("api", python, ["-m", "uvicorn", "app.main:app", "--reload", "--host", process.env.API_HOST || "127.0.0.1", "--port", process.env.API_PORT || "8000"], apiDir),
  startProcess("web", npm, ["--workspace", "apps/web", "run", "dev", "--", "--hostname", "127.0.0.1", "--port", "3002"], ROOT, true),
];

function shutdown() {
  log("system", "正在停止所有服务...");
  for (const child of children) {
    if (!child.killed) child.kill("SIGTERM");
  }
  process.exit(0);
}

process.on("SIGINT", shutdown);
process.on("SIGTERM", shutdown);
process.on("exit", shutdown);
