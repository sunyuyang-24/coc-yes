# COC Yes

在线 COC 跑团助手。项目目标是把房间、聊天、录音、角色卡、骰子、KP 管理和规则书检索整合成一个可持续扩展的跑团工作台。

## 当前阶段

当前已经完成项目规划和阶段 0 工程骨架：

- `apps/web`：Next.js 前端。
- `apps/api`：FastAPI 后端。
- `packages/shared`：前后端共享类型和 COC 常量。
- `scripts/dev.mjs`：一条命令同时启动前后端。

## 本地启动

先安装依赖：

```powershell
npm.cmd install
& .\apps\api\.venv\Scripts\python.exe -m pip install -r .\apps\api\requirements.txt
```

如果还没有后端虚拟环境，先创建：

```powershell
& 'C:\Users\27164\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m venv .\apps\api\.venv
```

启动开发环境：

```powershell
npm.cmd run dev
```

默认地址：

- 前端：http://127.0.0.1:3000
- 后端：http://127.0.0.1:8000/api/health

## 重要约定

- 不提交本地规则书 PDF、上传文件、规则索引和录音文件。
- 骰子结果后续必须由后端生成并写入日志。
- 规则查询后续必须基于本地授权 PDF 检索，回答要带来源和页码。
- 每完成一个大模块，及时提交并推送。
