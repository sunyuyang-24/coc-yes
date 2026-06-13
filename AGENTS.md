# AGENT.md — CoC Yes 项目开发指南

> 面向 AI Coding Agent 的项目上下文、技术栈、代码规范与协作约定。

---

## 1. 项目概览

**CoC Yes** 是一个为 **Call of Cthulhu 7th Edition（克苏鲁的呼唤 第七版）** 桌游跑团打造的在线协作 Web 应用。核心价值是把"房间、语音、角色卡、骰子、KP 管理、规则书检索"整合成一个即开即用的工作台。

- 后端：FastAPI + Python 3.10+（详见 [apps/api/app/main.py](file:///E:/ERE/Documents/Work/coc-yes/apps/api/app/main.py)）
- 前端：Next.js 16（Turbopack）+ TypeScript（详见 [apps/web/src/app/page.tsx](file:///E:/ERE/Documents/Work/coc-yes/apps/web/src/app/page.tsx)）
- 共享类型：`packages/shared` npm workspace 包（详见 [packages/shared/src/index.ts](file:///E:/ERE/Documents/Work/coc-yes/packages/shared/src/index.ts)）
- 数据持久化：SQLite（WAL 模式），启动时可自动从旧版 `rooms.json` 迁移（详见 [apps/api/app/core/db.py](file:///E:/ERE/Documents/Work/coc-yes/apps/api/app/core/db.py)）
- 语音：WebRTC Mesh + WebSocket Signaling（服务端仅做中继，不做 MCU）

---

## 2. 目录结构

```
coc-yes/
├── apps/
│   ├── api/                       # FastAPI 后端
│   │   ├── app/
│   │   │   ├── core/              # 基础设施层
│   │   │   │   ├── config.py         # 设置（环境变量解析）
│   │   │   │   ├── db.py             # SQLite 连接 + 迁移
│   │   │   │   ├── limiter.py        # IP 级请求限流
│   │   │   │   └── auth_middleware.py# JWT 鉴权中间件
│   │   │   └── modules/           # 业务层（按模块组织）
│   │   │       ├── auth/             # 注册/登录/JWT
│   │   │       ├── bootstrap/        # 启动信息
│   │   │       ├── characters/       # Excel 角色卡解析
│   │   │       ├── dice/             # COC 骰子引擎
│   │   │       ├── health/           # 健康检查
│   │   │       ├── rooms/            # 房间 / 聊天 / 信令 / 战斗 / 追逐
│   │   │       └── rules/            # 本地 PDF 规则书索引 & 搜索
│   │   └── requirements.txt
│   └── web/                       # Next.js 前端
│       └── src/
│           ├── app/                  # App Router
│           ├── components/           # React 组件
│           └── lib/                  # api.ts / auth.ts
├── packages/
│   └── shared/src/index.ts        # 前后端共享类型 & 常量
├── docs/                          # 产品/架构/路线图文档
├── scripts/
│   ├── dev.mjs                       # 并发启动前后端
│   └── dev-api.mjs
├── start.bat                      # Windows 一键启动
├── .env.example                   # 环境变量模板
└── package.json
```

---

## 3. 关键文件地图

| 关注点 | 文件路径 | 作用 |
|---|---|---|
| 应用入口 | [apps/api/app/main.py](file:///E:/ERE/Documents/Work/coc-yes/apps/api/app/main.py) | FastAPI 生命周期、中间件、路由装配、WebSocket 入口 |
| 配置 | [apps/api/app/core/config.py](file:///E:/ERE/Documents/Work/coc-yes/apps/api/app/core/config.py) | `Settings` 单例，读取环境变量 |
| 数据库 | [apps/api/app/core/db.py](file:///E:/ERE/Documents/Work/coc-yes/apps/api/app/core/db.py) | 表结构、SQLite WAL、`rooms.json → SQLite` 迁移 |
| 鉴权中间件 | [apps/api/app/core/auth_middleware.py](file:///E:/ERE/Documents/Work/coc-yes/apps/api/app/core/auth_middleware.py) | 解析 `Authorization: Bearer <token>`，注入 `request.state.user_id` |
| 限流 | [apps/api/app/core/limiter.py](file:///E:/ERE/Documents/Work/coc-yes/apps/api/app/core/limiter.py) | Token-bucket 风格的 IP 级限流 |
| 认证服务 | [apps/api/app/modules/auth/service.py](file:///E:/ERE/Documents/Work/coc-yes/apps/api/app/modules/auth/service.py) | bcrypt 哈希、JWT encode/decode、用户 CRUD |
| 认证路由 | [apps/api/app/modules/auth/router.py](file:///E:/ERE/Documents/Work/coc-yes/apps/api/app/modules/auth/router.py) | `/api/auth/register`、`/api/auth/login`、`/api/auth/me` |
| 骰子引擎 | [apps/api/app/modules/dice/roller.py](file:///E:/ERE/Documents/Work/coc-yes/apps/api/app/modules/dice/roller.py) | d100 COC 规则、对抗、推动、重伤、疯狂、武器卡壳 |
| 房间路由 | [apps/api/app/modules/rooms/router.py](file:///E:/ERE/Documents/Work/coc-yes/apps/api/app/modules/rooms/router.py) | HTTP API 主路由 + `room_socket` WebSocket 协程 |
| 房间状态 | [apps/api/app/modules/rooms/store.py](file:///E:/ERE/Documents/Work/coc-yes/apps/api/app/modules/rooms/store.py) | `RoomStore`（继承 CombatMixin / ChaseMixin / NpcMixin），RLock 保护 |
| 规则索引 | [apps/api/app/modules/rules/indexer.py](file:///E:/ERE/Documents/Work/coc-yes/apps/api/app/modules/rules/indexer.py) | PyMuPDF 抽取、关键词搜索、页码级 excerpt |
| 前端入口 | [apps/web/src/app/page.tsx](file:///E:/ERE/Documents/Work/coc-yes/apps/web/src/app/page.tsx) | 顶栏 + `RoomConsole` |
| 前端布局 | [apps/web/src/app/layout.tsx](file:///E:/ERE/Documents/Work/coc-yes/apps/web/src/app/layout.tsx) | HTML 框架、字体、meta、PWA 清单 |
| 共享类型 | [packages/shared/src/index.ts](file:///E:/ERE/Documents/Work/coc-yes/packages/shared/src/index.ts) | `RoomMember`, `DiceRollResult`, `CharacterCard`, `CombatState`, `ChaseState` 等 |
| 依赖清单 | [apps/api/requirements.txt](file:///E:/ERE/Documents/Work/coc-yes/apps/api/requirements.txt) | `fastapi`, `uvicorn`, `PyMuPDF`, `python-jose[cryptography]`, `bcrypt` |
| 环境变量 | [.env.example](file:///E:/ERE/Documents/Work/coc-yes/.env.example) | `API_HOST`, `API_PORT`, `API_CORS_ORIGINS`, `NEXT_PUBLIC_API_BASE_URL` |

---

## 4. 技术栈与版本约束

- **Python**：`>= 3.10`（大量使用 `X | None`、`dataclass`）
- **FastAPI**：`>= 0.115, < 1.0`
- **ASGI Server**：`uvicorn[standard]`
- **PDF 解析**：`PyMuPDF` (`import fitz`)
- **JWT**：`python-jose[cryptography]`（`jose.jwt`）
- **密码哈希**：`bcrypt`
- **Next.js**：`latest`（App Router + Turbopack）
- **React**：`latest`
- **TypeScript**：`latest`
- **随机数**：`secrets.SystemRandom()`（骰子不可预测）

---

## 5. 核心架构决策

### 5.1 后端模块组织

每个模块是一个目录，包含：

- `__init__.py`（可选，空文件）
- `router.py` — FastAPI `APIRouter`
- `service.py` — 纯函数 / 类的业务逻辑
- `schemas.py` — Pydantic v2 `BaseModel` 请求/响应
- `*.py` — 领域特定代码（例如 `rooms/store.py`, `dice/roller.py`, `rules/indexer.py`）

在 [main.py](file:///E:/ERE/Documents/Work/coc-yes/apps/api/app/main.py) 中统一 include_router，所有 HTTP 路由前缀 `/api`。

### 5.2 认证与授权

- **注册**：`POST /api/auth/register` → bcrypt 哈希 → 签发 HS256 JWT
- **登录**：`POST /api/auth/login` → 验证密码 → 签发 JWT
- **鉴权**：`AuthMiddleware` 对非 register/login 的 HTTP 请求读取 `Authorization: Bearer <token>`，解码后写 `request.state.user_id`；WebSocket 不在这里校验（由房间协议自己处理 member_id）
- **权限**：KP-only 命令（`webrtc_force_mute`, `webrtc_kick`, `activate`, `end`, `delete` 等）在路由或 socket 处理函数内部按 `member.role == "keeper"` 判定

⚠️ 生产部署务必覆盖 `JWT_SECRET`（默认 `coc-yes-dev-secret-change-in-production`）。

### 5.3 数据层

- **运行期数据库**：`data/runtime/rooms.db`（SQLite，WAL 模式）
- **表结构**（均见 [db.py](file:///E:/ERE/Documents/Work/coc-yes/apps/api/app/core/db.py)）：
  - `users(id, username, password_hash, display_name, created_at)`
  - `rooms(id, name, status, invite_code, password, room_theme, module_intro, summary, created_at, ended_at)`
  - `room_members(id, room_id, user_id, display_name, role, online, joined_at)`
  - `characters(id, room_id, owner_id, owner_name, data_json, created_at, updated_at)`
  - `messages(id, room_id, type, sender_id, sender_name, sender_role, content, data_json, created_at)`
  - `dice_rolls(id, room_id, roller_id, data_json, created_at)`
- **迁移**：首次启动若检测到 `data/runtime/rooms.json`，自动导入并把源文件重命名为 `*.migrated`
- **锁**：`threading.RLock` 保护内存状态（`RoomStore`）；SQLite 层由 `check_same_thread=False` 允许跨线程

### 5.4 实时通道（WebSocket）

- 入口：`GET /api/rooms/{room_id}/ws?member_id=...`
- 连接成功后立即发送 `{ type: "room_state", room: ... }` 全量快照
- 心跳：每 30 秒服务端发送 `{ type: "ping" }`，防止代理/防火墙断连
- 消息广播：所有变化（新消息、角色卡更新、成员上线、主题变更）由 `connection_manager.broadcast` 转发，并向所有在线成员推送 `{ type: "room_update", room: ... }`
- WebRTC 信令：
  - 点对点：`webrtc_offer`, `webrtc_answer`, `webrtc_ice`
  - 房间状态：`webrtc_mute`, `webrtc_unmute`, `webrtc_voice_join`, `webrtc_voice_leave`
  - KP 特权：`webrtc_force_mute`, `webrtc_kick`（服务端校验发送者角色）
- 断开：`manager.disconnect` → 标记 member offline → 广播离开

### 5.5 骰子引擎设计要点

文件：[apps/api/app/modules/dice/roller.py](file:///E:/ERE/Documents/Work/coc-yes/apps/api/app/modules/dice/roller.py)

- **表达式文法**：`^\s*(\d*)d(\d+)\s*([+-]\s*\d+)?\s*$`（大小写不敏感）
- **1d100 特殊分支**：额外处理 bonus/penalty dice（tens_rolls 多位十位骰，选择最小/最大）
- **成功等级**（CRB p79/p90）：
  - `1` → critical（大成功）
  - `total ≤ target // 5` → extreme（极难）
  - `total ≤ target // 2` → hard（困难）
  - `total ≤ target` → regular（普通）
  - `100` 或 `skill<50 且 total≥96` → fumble（大失败）
- **辅助规则 API**：`opposed_check`, `pushing_check`, `first_aid_check`, `medicine_check`, `major_wound_check`, `insanity_check`, `weapon_malfunction_check`

---

## 6. 前后端共享类型

`packages/shared/src/index.ts` 导出的类型需要保持与后端 JSON 序列化结果兼容。**任何修改都要同步前后端**。关键类型如下，供 Agent 做类型推断时参考：

```ts
RoomMemberRole = "keeper" | "player" | "spectator";
RoomDetail    = { id, name, status: "preparing"|"active"|"ended",
                  inviteCode, members, messages, rolls?, characters?,
                  moduleIntro?, combatState?, chaseState?, roomTheme? };
DiceRollResult = { id, expression, label, total, breakdown[],
                   targetValue, bonusPenalty, successLevel, successLabel,
                   hidden, createdAt, rollerId, rollerName, rollerRole };
CharacterCard  = { id, ownerId, ownerName, basic, attributes, status,
                   skills, weapons, background, experiences, spells,
                   keeperNotes, lockedFields?, isNpc?, history?,
                   createdAt, updatedAt };
CombatState    = { active, roundNumber, actors[], currentActorIndex, createdAt };
ChaseState     = { active, participants[], obstacles[], createdAt };
ChatMessage    = { id, type: "text"|"system"|"dice_roll"|"private"|"voice"|"attachment",
                   senderId, senderName, senderRole, content, roll?, replyTo?,
                   privateTo?, whisperTo?, mentionIds?, attachment?, createdAt };
```

---

## 7. 主要 API 接口一览

所有路由前缀 `/api`，WebSocket 例外。

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/auth/register` | 用户注册（用户名唯一），返回 `{ user, token }` |
| POST | `/auth/login` | 用户登录，返回 `{ user, token }` |
| GET  | `/auth/me` | 当前登录用户信息 |
| GET  | `/health` | 健康检查（不限流） |
| GET  | `/rooms/mine` | 绑定到当前 user_id 的房间列表 |
| POST | `/rooms` | 创建房间（KP 身份），返回 `{ room, currentMemberId }` |
| POST | `/rooms/join` | 邀请码加入，可选密码，返回 `{ room, currentMemberId }` |
| POST | `/rooms/{id}/bind` | 把一个匿名 member 绑定到已登录 user |
| GET  | `/rooms/{id}` | 房间快照，可选 `?member_id=` 做脱敏（去除私聊等） |
| POST | `/rooms/{id}/messages` | 发送文字/附件/回复/@提及 消息 |
| POST | `/rooms/{id}/rolls` | 投掷骰子（后端随机，防作弊） |
| POST | `/rooms/{id}/voice` | 上传语音消息（multipart，`duration`, `file`） |
| GET  | `/rooms/{id}/voice/{filename}` | 下载语音（防盗链：禁止 `..`） |
| POST | `/rooms/{id}/files` | 上传通用文件/图片（最大 10 MB，白名单扩展） |
| GET  | `/rooms/{id}/files/{filename}` | 下载通用文件 |
| POST | `/rooms/{id}/characters/upload` | 上传 Excel 角色卡，返回解析后的 `CharacterCard` |
| POST | `/rooms/{id}/characters/npc` | KP 创建 NPC 角色卡 |
| POST | `/rooms/{id}/characters/npc/text` | 从文本快速创建 NPC |
| PATCH| `/rooms/{id}/characters/{cid}` | 更新角色卡（基本信息、锁定字段、Keeper 备注、历史修订） |
| POST | `/rooms/{id}/characters/{cid}/delete` | 删除角色卡（KP 专属） |
| POST | `/rooms/{id}/characters/remove` | 移除成员绑定的角色卡 |
| POST | `/rooms/{id}/activate` | KP 激活房间（进入 active 状态） |
| POST | `/rooms/{id}/end` | KP 结束房间（生成 summary 草稿） |
| POST | `/rooms/{id}/delete` | KP 删除房间 |
| POST | `/rooms/{id}/theme` | 切换房间主题（`black`, `graphite`, `green`, `blue`, `red`, `sepia`） |
| POST | `/rooms/{id}/summary` | 保存 session 总结（KP 编辑） |
| GET  | `/rooms/{id}/summary` | 获取 session 总结，若不存在则自动生成 |
| PATCH| `/rooms/{id}/intro` | 保存模组简介（module_intro） |
| POST | `/rooms/{id}/messages/{mid}/delete` | KP 删除消息 |
| POST | `/combat/...` | 战斗回合管理（见 `router_combat.py`） |
| POST | `/chase/...`  | 追逐回合管理（见 `router_chase.py`） |
| POST | `/coc/...`    | 规则专用检定（对抗/推动/疯狂/重伤/卡壳，见 `router_coc.py`） |
| GET  | `/rules/search?q=` | 规则书关键词检索（基于本地授权 PDF 索引） |
| WS   | `/rooms/{id}/ws?member_id=...` | 房间实时通道 |

---

## 8. 本地开发指南

### 方式一：一键启动（Windows 推荐）

```bat
start.bat
```

脚本会：
1. 检查 Node.js 与 Python；
2. 从 `.env.example` 生成 `.env`；
3. `npm install` 安装前端依赖；
4. 为后端创建虚拟环境 `apps/api/.venv` 并安装 `requirements.txt`；
5. 并发启动前后端（脚本见 [scripts/dev.mjs](file:///E:/ERE/Documents/Work/coc-yes/scripts/dev.mjs)）。

### 方式二：手动命令行

```powershell
# 依赖
npm install
python -m venv apps/api/.venv
apps/api/.venv/Scripts/python.exe -m pip install -r apps/api/requirements.txt

# 环境
Copy-Item .env.example apps/api/.env
Copy-Item .env.example apps/web/.env.local

# 启动
npm run dev
```

启动后访问：
- 前端：`http://localhost:3001`
- API 文档：`http://127.0.0.1:8000/docs`
- 健康检查：`http://127.0.0.1:8000/api/health`

### 环境变量

参考 [.env.example](file:///E:/ERE/Documents/Work/coc-yes/.env.example)：

```
API_HOST=127.0.0.1
API_PORT=8000
API_CORS_ORIGINS=http://localhost:3000,http://127.0.0.1:3000
NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8000
JWT_SECRET=change-me-in-production
JWT_EXPIRE_DAYS=30
API_ADMIN_KEY=coc-yes-admin
```

---

## 9. 代码风格与命名约定

### 9.1 Python（后端）

- **解释器要求**：`>= 3.10`，允许 `X | None` 联合语法；禁用 `from __future__ import annotations` 之外的特殊编译指令
- **字符串引号**：双引号为主，单行字符串；多行 docstring 用三双引号
- **类型注解**：公开函数 / 方法必须标注；私有函数可酌情，但 Pydantic 模型必须全量字段标注
- **并发模型**：
  - FastAPI 路由用 `async def`，内部避免阻塞；磁盘/CPU 重活（如 `fitz.open`）放在同步函数里由 FastAPI 的线程池执行
  - `RoomStore` 内部用 `self._lock = RLock()` 保护写路径，读路径允许浅拷贝后再返回（`deepcopy(room)`）
  - `RateLimitMiddleware` 必须同时放行 WebSocket 连接，不要对 scope type=websocket 做限流
- **中间件顺序**（`main.py`）：`RateLimitMiddleware → AuthMiddleware → CORSMiddleware`（注意 FastAPI 中间件是 LIFO，代码里从上到下写对应"先添加的先触发出站"）

### 9.2 TypeScript（前端）

- **React 组件**：文件即组件，默认导出；子组件放在同目录或 `components/` 下
- **命名**：PascalCase 组件，camelCase 函数与变量，UPPER_CASE 常量
- **路径别名**：`@/components/*`, `@/lib/*`（在 Next.js `tsconfig.json` 里配置）
- **样式**：全局 CSS（`globals.css`, `room-layout.css`），不引入 Tailwind 等额外框架；主题通过 `html[data-background="black|green|blue|red|sepia|graphite"]` 切换

### 9.3 跨文件 / 跨仓库约定

- **前端请求**：统一走 `src/lib/api.ts` 的 `fetchApi(url, options)`，自动附 `Authorization: Bearer <localStorage token>`，401 自动清理
- **WebSocket 客户端**：始终传递 `member_id` 查询参数；收到 `room_update` 时用返回的 `room` 对象整体替换前端状态，不要做增量 diff（减少竞态）
- **敏感字段**：`room.password` 在任何 API 响应中必须被显式 `pop`；`CharacterCard.lockedFields` 只有 keeper 可写
- **文件上传**：音频 50 MB、其他文件 10 MB；扩展名白名单 + content-type 校验；URL 必须经过 `settings.data_dir` 前缀且禁止 `..` 穿越

---

## 10. 业务规则摘要（便于 Agent 推理）

### 10.1 房间生命周期

```
preparing → active → ended
   ↑          ↑         ↑
 创建      KP activate  KP end
```

- `preparing`：邀请码加入；允许最多 50 成员；允许上传/编辑角色卡、简介；**不可发送骰子**（由前端 + 后端双校验）
- `active`：允许聊天、骰子、战斗、追逐；KP 可 force_mute/kick
- `ended`：只读，允许查看摘要；房间仍在数据库中保留

### 10.2 成员角色

| role | 能力 |
|---|---|
| `keeper` | 所有写权限（编辑任何角色卡、激活/结束房间、force_mute、kick、删除消息、切换主题、保存模组简介/总结） |
| `player` | 聊天、发骰子（非 hidden）、管理自己的角色卡（除非 KP 锁定） |
| `spectator` | 只读（不发消息、不掷骰） |

### 10.3 COC 7e 核心规则（骰子相关）

- **检定结果**：`total = 1d100`（00=100），越小越好
- **奖励骰 / 惩罚骰**：额外掷 N 个十位骰，取有利/不利结果
- **成功等级**：大成功（1）/ 极难（≤ skill/5）/ 困难（≤ skill/2）/ 普通（≤ skill）/ 失败 / 大失败（100 或 skill<50 且 ≥96）
- **推动（Pushing）**：失败且非大失败可再掷一次，失败后果加重
- **对抗（Opposed）**：比较成功等级，同级比较技能值；闪避平局防守方胜，反击平局攻击方胜
- **重伤**：单次伤害 ≥ HP/2
- **疯狂**：
  - 单次 SAN 损失 ≥ 5 → INT 检定，成功→临时疯狂
  - 单日累计 ≥ 原 SAN 1/5 → 不定期疯狂
  - SAN 归零 → 永久疯狂，调查员退场
- **武器卡壳**：出目 ≥ `malf_value`（默认 96）

### 10.4 战斗 & 追逐模块

- **CombatMixin**：维护 `CombatState`，按 DEX 降序排队，`CombatActionRequest` 驱动动作（attack/dodge/maneuver/fight_back）
- **ChaseMixin**：维护 `ChaseState`，参与者分为 `pursuer`/`fugitive`，含位置、障碍（hazard/barrier），动作包括 speed_check / maneuver / conflict

---

## 11. 安全清单

Agent 在做任何改动时，请对照以下点：

1. **JWT**：不要把 `JWT_SECRET` 写死到提交的代码里，读 `os.getenv`
2. **密码**：用户密码必须走 `bcrypt.hashpw`；房间密码为可选明文比较（因为是非登录身份的房间密码，不涉及账户安全）
3. **SQL 注入**：统一使用 `db.execute("... ? ...", (params,))` 的占位符语法；禁止字符串拼接 SQL
4. **路径穿越**：`/rooms/{id}/voice/{filename}` 和 `/rooms/{id}/files/{filename}` 必须检查 `..` 和绝对路径
5. **上传大小**：在 FastAPI 层 + `limiter` 层 + 文件大小判断三处做双重校验
6. **XSS**：聊天 content、角色卡 `basic`、`keeperNotes`、`moduleIntro`、`summary` 等文本字段**在前端以纯文本渲染**（`textContent` / React children），不要 `dangerouslySetInnerHTML`
7. **WebSocket 身份**：`member_id` 只用于绑定房间成员，KP 的操作需要再通过 `members[i].role == "keeper"` 二次校验，不能仅靠查询参数信任
8. **骰子不可伪造**：骰子结果必须由后端 `secrets.SystemRandom()` 生成并写入 `dice_rolls` 表；前端展示仅读取 `rolls` 列表
9. **规则书 PDF**：本地索引，不上传云端；索引 JSON 与 PDF 本身都在 `.gitignore` 内

---

## 12. 常见开发任务的操作指引

### 12.1 新增一个 HTTP 接口

1. 在对应 `modules/<name>/schemas.py` 定义请求/响应 `BaseModel`（字段用 snake_case，前端使用时自动兼容 camelCase JSON）
2. 在 `modules/<name>/router.py` 新增 `@router.<method>(...)`，对外部暴露统一挂在 `/api` 下
3. 在 `main.py` 的 `app.include_router(...)` 中按已有顺序追加
4. 若需鉴权，在函数内 `user_id = getattr(request.state, "user_id", None)`，缺失时返回 `HTTPException(status_code=401)`
5. 若涉及房间写操作，记得在处理末尾 `await manager.broadcast(room_id, {"type": "room_update", "room": ...}, store)`

### 12.2 新增一种骰子规则

1. 在 `apps/api/app/modules/dice/roller.py` 新增一个纯函数（输入基本数值，输出结构化 dict）
2. 在 `apps/api/app/modules/rooms/router_coc.py`（或 `router.py`）新增路由调用它，并 `store.add_dice_roll(...)` 持久化
3. 在 `packages/shared/src/index.ts` 补充返回类型
4. 前端对应组件（例如 `san-check-panel.tsx`, `combat-panel.tsx`）中展示结果

### 12.3 修改共享类型

1. 先改 `packages/shared/src/index.ts`
2. 后端：检查 `modules/rooms/schemas.py`、`modules/characters/parser.py`、`modules/dice/schemas.py` 是否需要同步调整
3. 前端：`npm run dev` 下 HMR 会自动生效；类型检查 `npm --workspace apps/web run tsc --noEmit`

### 12.4 新增主题

1. `packages/shared` 的 `RoomDetail.roomTheme` 联合类型中加入新值
2. `apps/web/src/app/globals.css` 或 `room-layout.css` 中为 `html[data-background="<value>"]` 定义变量
3. `apps/api/app/modules/rooms/router.py` 中 `POST /rooms/{id}/theme` 无需修改（它只把值原样写回）

### 12.5 部署 Checklist

- [ ] `JWT_SECRET` / `API_ADMIN_KEY` 已替换
- [ ] `API_CORS_ORIGINS` 限制为真实域名
- [ ] SQLite 数据目录挂到持久卷（或配置 PostgreSQL 替代）
- [ ] 上传目录 `data/runtime/uploads` 单独备份策略
- [ ] 反向代理启用 WebSocket 协议升级（`Upgrade: websocket` / `Connection: Upgrade`）
- [ ] Nginx/Caddy 将真实客户端 IP 通过 `X-Forwarded-For` 传给后端，并让 `RateLimitMiddleware` 信任代理 IP（见 `limiter.py` 的 `_trusted_proxies` 扩展点）

---

## 13. 文档与相关文件

- 产品需求：[docs/product-requirements.md](file:///E:/ERE/Documents/Work/coc-yes/docs/product-requirements.md)
- 架构说明：[docs/architecture.md](file:///E:/ERE/Documents/Work/coc-yes/docs/architecture.md)
- MVP 路线：[docs/mvp-roadmap.md](file:///E:/ERE/Documents/Work/coc-yes/docs/mvp-roadmap.md)
- 功能 Backlog：[docs/feature-backlog.md](file:///E:/ERE/Documents/Work/coc-yes/docs/feature-backlog.md)
- 调查员体验报告：[docs/investigator-experience-report.md](file:///E:/ERE/Documents/Work/coc-yes/docs/investigator-experience-report.md)

---

## 14. 给 Agent 的操作边界

1. **先读相关文件再修改**：改路由前读 `main.py` + `router.py`；改数据前读 `db.py` + `store.py`；改类型前读 `packages/shared/src/index.ts`
2. **保持单文件风格一致**：新增函数命名与邻近函数一致；不要混合引号风格、缩进风格
3. **不提交敏感数据**：`data/`、`*.pdf`、`.env`、`*.migrated` 已在 `.gitignore`；新增本地大文件前先确认忽略
4. **不引入新依赖除非必要**：如需引入，更新 `requirements.txt` 或 `apps/web/package.json`，并在本 AGENT.md 的 §4 同步
5. **接口变更要同步前端**：尤其是 `/api/rooms/{id}/ws` 的消息类型、`room` 对象字段——任何字段改名都要改前端对应读取位置
6. **测试要点**：骰子表达式（普通、bonus/penalty、边界值）、对抗检定平局分支、SAN 归零、NPC 创建/编辑、角色卡锁定字段、KP 权限（`force_mute`、`kick`、`delete`）

---

祝跑团愉快！⚅
