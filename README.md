<p align="center">
  <img src="https://img.shields.io/badge/CoC_7th-Run_Table-1a1a1a?style=for-the-badge&logo=data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCAyNCAyNCI+PHBhdGggZmlsbD0id2hpdGUiIGQ9Ik0xMiAyQzYuNDggMiAyIDYuNDggMiAxMnM0LjQ4IDEwIDEwIDEwIDEwLTQuNDggMTAtMTBTMTcuNTIgMiAxMiAyem0wIDE4Yy00LjQxIDAtOC0zLjU5LTgtOHMzLjU5LTggOC04IDggMy41OSA4IDgtMy41OSA4LTggOHptMC0xNGMtMy4zMSAwLTYgMi42OS02IDZzMi42OSA2IDYgNiA2LTIuNjkgNi02LTIuNjktNi02LTZ6Ii8+PC9zdmc+" alt="CoC 7th" />
  <br/>
  <img src="https://img.shields.io/badge/Next.js-16-black?logo=nextdotjs" alt="Next.js" />
  <img src="https://img.shields.io/badge/FastAPI-0.115-009688?logo=fastapi&logoColor=white" alt="FastAPI" />
  <img src="https://img.shields.io/badge/TypeScript-5-3178c6?logo=typescript&logoColor=white" alt="TypeScript" />
  <img src="https://img.shields.io/badge/SQLite-WAL-003B57?logo=sqlite&logoColor=white" alt="SQLite" />
  <img src="https://img.shields.io/badge/Auth-JWT-ff6c2c?logo=jsonwebtokens&logoColor=white" alt="JWT" />
  <img src="https://img.shields.io/badge/WebRTC-voice-333?logo=webrtc" alt="WebRTC" />
  <img src="https://img.shields.io/badge/license-MIT-green" alt="License" />
</p>

# CoC Yes — 在线克苏鲁的呼唤跑团助手

一个专为 **Call of Cthulhu 7th Edition** 桌游跑团打造的在线协作空间。整合房间管理、实时语音、角色卡、骰子引擎、战斗/追逐系统、规则检索和 JWT 账号系统，即开即用。

## 功能特性

| 功能 | 说明 |
|---|---|
| 账号系统 | JWT 注册/登录，跨会话保留历史房间，Guest 兼容 |
| 房间管理 | 一键创建跑团房间，6 位邀请码加入，KP / 玩家 / 旁观三种角色 |
| 实时聊天 | WebSocket 文字聊天，支持 @提及、私聊、悄悄话、引用回复、文件/图片上传 |
| 实时语音 | WebRTC 网状语音通话，KP 全员静音 / 强制静音 / 踢出 |
| 骰子引擎 | 后端结算，d100 检定、奖励/惩罚骰、对抗检定、孤注一掷、结构化技能/属性检定 |
| COC 进阶规则 | 对抗、急救、医学、重伤、精神检定、武器故障、SAN 检定（临时/不定/永久疯狂） |
| 战斗系统 | 按 DEX 排序先攻，攻击/闪避/反击/战术动作，贯穿武器、极限伤害、重伤判定 |
| 追逐系统 | 速度检定、机动推进、冲突对抗，障碍物与位置追踪 |
| 角色卡 | 上传 Excel 角色卡自动解析，属性/技能一键检定，KP 编辑/锁定/备注 |
| NPC 创建 | 手动创建或从自由文本解析 NPC 属性/技能/武器 |
| KP 控制台 | 暗骰、编辑角色卡、模块引言、会话总结（Markdown 导出） |
| 界面主题 | 5 种纯色背景主题（黑/石墨/墨绿/深蓝/暗红） |
| 规则书检索 | 本地 PDF 全文检索，准确引用页码和来源 |
| 语音消息 | 浏览器录音上传，支持播放与进度控制 |
| 数据持久化 | SQLite WAL 模式，内存缓存 + 磁盘双写，旧 JSON 数据自动迁移 |

## 技术栈

| 层 | 技术 |
|---|---|
| 前端 | Next.js 16 + TypeScript |
| 后端 | FastAPI + Python 3.12 |
| 数据库 | SQLite (WAL 模式) |
| 认证 | JWT (HS256) + bcrypt |
| 实时通信 | WebSocket + WebRTC (mesh) |
| 文件解析 | PyMuPDF (PDF 检索) + 纯 Python XLSX 解析 |

## 项目结构

```
coc-yes/
  apps/
    api/                      # FastAPI 后端
      app/
        main.py               # 应用入口，7 个 Router 注册，WebSocket 端点
        core/
          config.py           # 配置（JWT secret、CORS、数据目录）
          db.py               # SQLite WAL 连接 + Schema + rooms.json 迁移
          auth_middleware.py  # JWT 认证 ASGI 中间件
          limiter.py          # Token-bucket 限流（120 req/min/IP）
        modules/
          auth/               # 注册/登录/me（bcrypt + JWT）
          rooms/               # 核心房间模块
            router.py          #   25 个 REST 端点 + WebSocket
            router_combat.py   #   战斗路由（5 端点）
            router_chase.py    #   追逐路由（4 端点）
            router_coc.py      #   COC 7e 进阶规则（10 端点）
            store.py            #   RoomStore 核心 CRUD
            store_combat.py    #   CombatMixin
            store_chase.py     #   ChaseMixin
            store_npc.py       #   NpcMixin
            connection_manager.py  # WebSocket 连接管理
            schemas.py         # Pydantic 请求/响应模型
            deps.py            # 共享单例依赖
          dice/                # 骰子结算引擎
          characters/          # Excel 角色卡解析
          rules/               # PDF 规则书检索 + 索引管理
          bootstrap/           # 构建阶段信息
          health/              # 健康检查
  apps/
    web/                       # Next.js 前端
      src/
        app/                   # 布局 + 首页路由 + CSS
        components/
          room-console.tsx     #   主应用组件（~60 状态，WebSocket，所有操作）
          room-setup.tsx       #   大厅：登录门控 + 我的房间 + 创建/加入
          login-panel.tsx      #   登录/注册表单
          character-card-view.tsx  # 角色卡展示与编辑
          combat-panel.tsx     #   战斗轮次管理
          chase-panel.tsx      #   追逐管理
          san-check-panel.tsx  #   SAN 检定
          rules-search-panel.tsx   # 规则书检索
          summary-panel.tsx    #   会话总结编辑器
          voice-room.tsx       #   WebRTC 语音房间
          voice-recorder.tsx   #   录音上传
          voice-message.tsx    #   语音消息播放
          settings-panel.tsx   #   用户设置（主题、音效等）
          dice-roll-view.tsx   #   骰子结果展示
          api-status.tsx       #   API 在线状态指示器
          error-boundary.tsx   #   错误边界
        lib/
          api.ts               #   类型化 HTTP 客户端（自动附加 JWT）
          auth.ts              #   Token 管理 + login/register
  packages/
    shared/                    # 前后端共享类型（~25 类型 + COC 常量）
  scripts/
    dev.mjs                    # 前后端并发启动
    dev-api.mjs                # 后端单独启动
  start.bat                    # Windows 一键启动
  data/
    runtime/                   # rooms.db + rooms.json（旧格式）
    uploads/                   # 用户上传文件
```

## 本地启动

### 方式一：一键启动（推荐）

双击项目根目录的 `start.bat`，脚本会自动：
1. 检查 Node.js 和 Python 环境
2. 自动生成 `.env` 配置文件
3. 自动安装缺失的依赖（npm + pip）
4. 同时启动前后端服务

```powershell
.\start.bat
```

### 方式二：命令行启动

```powershell
npm install
python -m venv apps\api\.venv
apps\api\.venv\Scripts\python.exe -m pip install -r apps\api\requirements.txt
copy .env.example apps\api\.env
copy .env.example apps\web\.env.local
npm run dev
```

启动后访问：
- 前端页面：http://localhost:3002
- 后端 API：http://127.0.0.1:8000/api/health
- API 文档：http://127.0.0.1:8000/docs

## API 接口速览

### Auth（认证）
| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/api/auth/register` | 注册（username, password, displayName）→ user + JWT |
| POST | `/api/auth/login` | 登录 → user + JWT |
| GET | `/api/auth/me` | 获取当前用户信息（需 Bearer Token） |

### Rooms（房间核心）
| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/rooms/mine` | 我的历史/活跃房间（需认证） |
| POST | `/api/rooms/{id}/bind` | 绑定 guest 成员到账号 |
| POST | `/api/rooms` | 创建房间 |
| POST | `/api/rooms/join` | 邀请码加入房间 |
| GET | `/api/rooms/{id}` | 获取房间详情（?member_id= 可获取脱敏数据） |
| POST | `/api/rooms/{id}/messages` | 发送消息（支持回复/私聊/悄悄话/@提及/附件） |
| POST | `/api/rooms/{id}/messages/{mid}/delete` | 删除消息（KP 或本人） |
| POST | `/api/rooms/{id}/rolls` | 投掷骰子 |
| POST | `/api/rooms/{id}/characters/upload` | 上传 Excel 角色卡 |
| POST | `/api/rooms/{id}/characters/npc` | 创建 NPC |
| POST | `/api/rooms/{id}/characters/npc/text` | 自由文本解析创建 NPC |
| PATCH | `/api/rooms/{id}/characters/{cid}` | KP 编辑角色卡 |
| POST | `/api/rooms/{id}/characters/remove` | 移除自己的角色卡 |
| POST | `/api/rooms/{id}/characters/{cid}/delete` | KP 删除角色/NPC |
| POST | `/api/rooms/{id}/voice` | 上传语音消息（≤50MB） |
| GET | `/api/rooms/{id}/voice/{filename}` | 播放语音文件 |
| POST | `/api/rooms/{id}/files` | 上传文件/图片（≤10MB） |
| GET | `/api/rooms/{id}/files/{filename}` | 下载文件 |
| POST | `/api/rooms/{id}/activate` | KP 激活房间（preparing → active） |
| POST | `/api/rooms/{id}/theme` | KP 设置房间主题 |
| POST | `/api/rooms/{id}/end` | KP 结束房间 |
| POST | `/api/rooms/{id}/delete` | KP 删除房间 |
| GET | `/api/rooms/{id}/summary` | 获取会话总结 |
| POST | `/api/rooms/{id}/summary` | KP 保存总结草稿 |
| PATCH | `/api/rooms/{id}/intro` | KP 更新模块引言 |
| WS | `/api/rooms/{id}/ws` | 房间实时推送（WebSocket） |

### Combat（战斗）
| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/api/rooms/{id}/combat/start` | KP 开始战斗 |
| GET | `/api/rooms/{id}/combat/state` | 获取战斗状态 |
| POST | `/api/rooms/{id}/combat/action` | 执行战斗动作（attack/dodge/fight_back/maneuver） |
| POST | `/api/rooms/{id}/combat/end` | KP 结束战斗 |

### Chase（追逐）
| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/api/rooms/{id}/chase/start` | KP 开始追逐 |
| GET | `/api/rooms/{id}/chase/state` | 获取追逐状态 |
| POST | `/api/rooms/{id}/chase/action` | 执行追逐动作（speed_check/maneuver/conflict） |
| POST | `/api/rooms/{id}/chase/end` | KP 结束追逐 |

### COC 7e 进阶规则
| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/api/rooms/{id}/coc/opposed` | 对抗检定 |
| POST | `/api/rooms/{id}/coc/heal` | 治疗检定（急救/医学） |
| POST | `/api/rooms/{id}/coc/majorwound` | 重伤判定 |
| POST | `/api/rooms/{id}/coc/insanity` | 疯狂检定 |
| POST | `/api/rooms/{id}/coc/malfunction` | 武器故障 |
| POST | `/api/rooms/{id}/coc/pushing` | 孤注一掷 |
| POST | `/api/rooms/{id}/rolls/check` | 结构化技能/属性检定（从角色卡） |
| POST | `/api/rooms/{id}/rolls/san-check` | SAN 检定（临时/不定/永久疯狂） |

### Rules（规则书）
| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/rules/index-status` | 索引状态 |
| POST | `/api/rules/search` | 全文检索（keyword → 页码+摘录） |
| POST | `/api/rules/rebuild-index` | 重建索引（需 Admin Key） |

## 重要约定

- 骰子结果必须由后端生成，前端仅请求和展示
- 规则查询基于本地授权 PDF 检索，回答带页码和来源
- 不提交 PDF 规则书、上传文件、规则索引和录音文件
- 角色卡密码在所有 API 响应中自动剥离
- WebRTC force_mute / kick 仅 KP 可执行
- 只有无内容的 abandoned "preparing" 房间会被自动清理
