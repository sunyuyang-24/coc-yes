# COC Yes

在线 COC 跑团助手。项目目标是把房间、聊天、录音、角色卡、骰子、KP 管理和规则书检索整合成一个可持续扩展的跑团工作台。

## 当前阶段

当前已经完成项目规划、阶段 0 工程骨架、阶段 1 房间与文字聊天、阶段 2 可信骰子，并开始落地阶段 3 角色卡上传与解析：

- `apps/web`：Next.js 前端。
- `apps/api`：FastAPI 后端。
- `packages/shared`：前后端共享类型和 COC 常量。
- `scripts/dev.mjs`：一条命令同时启动前后端。
- 房间模块：创建房间、邀请码加入、成员列表、聊天消息、WebSocket 实时同步。
- 骰子模块：后端结算骰子表达式、COC d100 检定、奖励/惩罚骰、投掷结果进入聊天。
- 界面偏好：默认纯黑背景，并支持深灰、墨绿、深蓝、暗红等纯色背景切换。
- 角色卡模块：上传当前 COC 七版 Excel 模板，解析基础信息、属性、技能、武器和背景摘要。
- KP 管理：KP 可以编辑角色卡基础字段、属性值和 KP 备注。
- 角色卡检定：可从角色卡属性和技能预览直接发起 COC d100 检定。

## 本地启动

### 方式一：一键启动（推荐）

双击项目根目录的 `start.bat`，脚本会自动完成：
1. 检查 Node.js 和 Python 环境
2. 自动生成 `.env` 配置文件
3. 自动安装缺失的依赖（Node 和 Python）
4. 同时启动前后端服务

```powershell
.\start.bat
```

### 方式二：命令行启动

```powershell
# 1. 安装依赖（首次运行）
npm install
python -m venv apps\api\.venv
apps\api\.venv\Scripts\python.exe -m pip install -r apps\api\requirements.txt

# 2. 生成配置文件（首次运行会自动创建，也可手动复制）
copy .env.example apps\api\.env
copy .env.example apps\web\.env.local

# 3. 启动
npm run dev
```

启动后访问：

- 前端页面：http://localhost:3000
- 后端 API：http://127.0.0.1:8000/api/health
- API 文档：http://127.0.0.1:8000/docs


## 重要约定

- 不提交本地规则书 PDF、上传文件、规则索引和录音文件。
- 骰子结果后续必须由后端生成并写入日志。
- 规则查询后续必须基于本地授权 PDF 检索，回答要带来源和页码。
- 每完成一个大模块，及时提交并推送。
