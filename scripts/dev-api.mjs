import { existsSync } from "node:fs";
import { join } from "node:path";
import { spawn } from "node:child_process";

const root = process.cwd();
const apiDir = join(root, "apps", "api");
const venvPython = process.platform === "win32"
  ? join(apiDir, ".venv", "Scripts", "python.exe")
  : join(apiDir, ".venv", "bin", "python");

const python = process.env.PYTHON || (existsSync(venvPython) ? venvPython : "python");
const host = process.env.API_HOST || "127.0.0.1";
const port = process.env.API_PORT || "8000";

const child = spawn(
  python,
  ["-m", "uvicorn", "app.main:app", "--reload", "--host", host, "--port", port],
  {
    cwd: apiDir,
    stdio: "inherit",
    shell: false
  }
);

child.on("exit", (code) => {
  process.exit(code ?? 0);
});
