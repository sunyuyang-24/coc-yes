# CoC Yes 架构文档

## 1. 项目概述

CoC Yes 是一个面向 Call of Cthulhu 7th Edition 桌游跑团的在线协作工作台。目前已实现完整的 MVP 功能：房间管理、实时文字/语音聊天、角色卡解析、骰子引擎、战斗/追逐系统、COC 7e 进阶规则、JWT 账号系统、规则书检索和会话总结。

## 2. 技术栈（当前实施）

| 层 | 技术 | 状态 |
|---|---|---|
| 前端 | Next.js 16 + React + TypeScript | 已实施 |
| 后端 | FastAPI + Python 3.12 | 已实施 |
| 数据库 | SQLite WAL 模式 | 已实施 |
| 认证 | JWT (HS256) + bcrypt (passlib) | 已实施 |
| 实时通信 | WebSocket (聊天/状态) + WebRTC mesh (语音) | 已实施 |
| 文件存储 | 本地 `data/uploads/` | 已实施 |
| 文件解析 | 纯 Python XLSX (角色卡) + PyMuPDF (规则书 PDF) | 已实施 |
| 共享类型 | TypeScript monorepo `@coc-yes/shared` | 已实施 |

## 3. 持久化架构

```
请求 → FastAPI Router → AuthMiddleware (JWT 验证)
                            ↓
                      RoomStore (内存 _state + SQLite 双写)
                            ↓              ↓
                      self._state      SQLite (rooms.db)
                      (读缓存)          (WAL 模式)
```

- **读路径：** 启动时从 SQLite 加载全量到内存 `_state`，后续读取走内存（O(1) 字典查找）
- **写路径：** 每次 mutation 同时更新内存 `_state` 和 SQLite（逐表 upsert）
- **回退机制：** 如果 SQLite 未初始化，自动回退到 `rooms.json` 读写
- **迁移：** 首次启动时自动从 `rooms.json` 迁移数据到 SQLite，完成后重命名为 `.json.migrated`

## 4. 数据库 Schema

```sql
-- 用户
CREATE TABLE users (
    id TEXT PRIMARY KEY,           -- UUID
    username TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    display_name TEXT NOT NULL,
    created_at TEXT NOT NULL
);

-- 房间
CREATE TABLE rooms (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'preparing',  -- preparing|active|ended
    invite_code TEXT UNIQUE NOT NULL,
    password TEXT,
    room_theme TEXT DEFAULT 'black',
    module_intro TEXT,
    summary TEXT,                  -- JSON
    created_at TEXT NOT NULL,
    ended_at TEXT
);

-- 成员
CREATE TABLE room_members (
    id TEXT PRIMARY KEY,
    room_id TEXT NOT NULL REFERENCES rooms(id),
    user_id TEXT REFERENCES users(id),  -- NULL = guest
    display_name TEXT NOT NULL,
    role TEXT NOT NULL,            -- keeper|player|spectator
    online INTEGER NOT NULL DEFAULT 0,
    joined_at TEXT NOT NULL
);

-- 角色卡 (data_json 存完整 CharacterCard)
CREATE TABLE characters (
    id TEXT PRIMARY KEY,
    room_id TEXT NOT NULL REFERENCES rooms(id),
    owner_id TEXT,
    owner_name TEXT,
    data_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

-- 消息 (data_json 存 roll/replyTo/attachment/privateTo/whisperTo 等额外字段)
CREATE TABLE messages (
    id TEXT PRIMARY KEY,
    room_id TEXT NOT NULL REFERENCES rooms(id),
    type TEXT NOT NULL,
    sender_id TEXT,
    sender_name TEXT NOT NULL,
    sender_role TEXT NOT NULL,
    content TEXT NOT NULL DEFAULT '',
    data_json TEXT,
    created_at TEXT NOT NULL
);

-- 骰子记录 (独立于消息存储)
CREATE TABLE dice_rolls (
    id TEXT PRIMARY KEY,
    room_id TEXT NOT NULL REFERENCES rooms(id),
    roller_id TEXT NOT NULL,
    data_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);
```

## 5. 后端模块架构

### 5.1 RoomStore 类层次

```
RoomStore (store.py)
├── CombatMixin (store_combat.py)   — 战斗轮次管理
├── ChaseMixin (store_chase.py)     — 追逐轮次管理
└── NpcMixin (store_npc.py)         — NPC 创建/文本解析
```

**设计决策：** Mixin 模式将 1294 行的巨石类拆分为 4 个文件，各文件职责独立，可并行开发。

### 5.2 Router 拆分

```
main.py 注册 7 个 Router:
├── auth_router      → /api/auth/*      (3 端点)
├── health_router    → /api/health      (1 端点)
├── bootstrap_router → /api/bootstrap   (1 端点)
├── rooms_router     → /api/rooms/*     (25 REST + 1 WS)
├── combat_router    → /api/rooms/*/combat/*  (5 端点)
├── chase_router     → /api/rooms/*/chase/*   (4 端点)
├── coc_router       → /api/rooms/*/coc/* + /api/rooms/*/rolls/*  (10 端点)
└── rules_router     → /api/rules/*     (3 端点)
```

所有子 Router 通过 `deps.py` 共享 `store` 和 `manager` 单例，避免循环导入。

### 5.3 认证流程

```
1. POST /api/auth/register  → bcrypt 哈希密码 → 插入 users 表 → 返回 JWT
2. POST /api/auth/login     → bcrypt 验证 → 返回 JWT
3. 前端 apiRequest() 自动附加 Authorization: Bearer <token>
4. AuthMiddleware 验证 JWT → 注入 request.state.user_id
5. 无需认证的路径放行: /api/auth/register, /api/auth/login, /api/health
6. 未认证用户以 guest 身份使用（member.userId = null）
7. POST /api/rooms/{id}/bind → 将 guest member 绑定到注册用户
```

### 5.4 安全措施

- **密码剥离：** `get_room_sanitized()` 移除 room.password；所有 create/join 响应移除密码
- **WebSocket 隔离：** `broadcast()` 按 member 过滤隐藏骰子和私聊消息
- **WebRTC 权限：** `webrtc_force_mute` 和 `webrtc_kick` 仅 KP 可执行，非 KP 静默丢弃
- **房间清理：** 仅清理无内容、无在线成员、空闲 >1 小时的 "preparing" 房间
- **限流：** Token-bucket 120 req/min/IP

## 6. 前端组件架构

```
RoomConsole (主应用组件)
├── RoomSetup (大厅)
│   ├── LoginPanel (登录/注册)
│   ├── 我的房间列表
│   ├── CreateRoomForm
│   └── JoinRoomForm
├── 聊天区
│   ├── 消息列表 (文字/骰子/语音/附件)
│   ├── 输入框 (支持 @提及、文件上传)
│   └── 骰子面板
├── 右侧面板
│   ├── CharacterCardView (角色卡展示/编辑)
│   ├── RulesSearchPanel (规则书检索)
│   └── SummaryPanel (会话总结)
├── 模态框
│   ├── CombatPanel (战斗)
│   ├── ChasePanel (追逐)
│   ├── SanCheckPanel (SAN 检定)
│   └── SettingsPanel (设置)
├── 语音
│   ├── VoiceRoom (WebRTC 通话)
│   ├── VoiceRecorder (录音)
│   └── VoiceMessage (播放)
└── 辅助
    ├── ApiStatus (API 在线状态)
    └── ErrorBoundary (错误边界)
```

**状态管理方案：** 所有状态集中在 `RoomConsole`（~60 个 useState），通过 props 向下传递。WebSocket 连接带指数退避自动重连（3s → 30s）。

## 7. 骰子引擎

### 支持的操作

| 功能 | 实现 |
|---|---|
| 通用表达式 | `roll_dice("1d100")`, `roll_dice("2d6+3")` |
| COC 检定 | 大成功(1)、极难(≤目标/5)、困难(≤目标/2)、普通(≤目标)、大失败(100 或 96-100) |
| 奖励/惩罚骰 | 0-9 十位数骰子，取最佳/最差 |
| 对抗检定 | `opposed_check()` — 比较成功等级，相同等级高技能胜 |
| 孤注一掷 | `pushing_check()` — 已失败且未孤注过 |
| 急救 | 恢复 1 HP |
| 医学 | 恢复 1d3 HP |
| 重伤 | 单次伤害 ≥ HP/2 |
| 疯狂 | 永久(SAN=0)、临时(损失≥5 触发 INT 检定)、不定(累计日损失≥1/5 SAN) |
| 武器故障 | 检定值 ≥ 故障值（默认 96） |

## 8. MVP 实施状态

### 已完成
- [x] 房间创建/邀请码加入/角色管理
- [x] JWT 注册/登录 + Guest 兼容
- [x] WebSocket 实时文字聊天（@提及/私聊/悄悄话/引用/附件）
- [x] WebRTC mesh 语音通话（静音/强制静音/踢出）
- [x] 骰子引擎 + COC 7e 进阶规则
- [x] Excel 角色卡解析 + KP 编辑/锁定/备注
- [x] NPC 创建（手动 + 自由文本解析）
- [x] 战斗系统（先攻/攻击/闪避/反击/机动/伤害/重伤）
- [x] 追逐系统（速度检定/机动/冲突/障碍物）
- [x] SAN 检定（临时/不定/永久疯狂）
- [x] 规则书 PDF 全文检索
- [x] 语音消息录音/上传/播放
- [x] 会话总结（统计 + Markdown 编辑 + 导出）
- [x] 5 种界面主题
- [x] SQLite 持久化 + 旧 JSON 数据迁移
- [x] 限流 + 安全措施

### 规划中
- [ ] LiveKit 替代 WebRTC mesh（更好的多人语音体验）
- [ ] 角色卡版本历史
- [ ] 地图/手稿/NPC 卡片
- [ ] 跑团战役归档
- [ ] 玩家个人角色库
- [ ] 移动端适配
