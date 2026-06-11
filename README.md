<p align="center">
  <img src="https://img.shields.io/badge/CoC_7th-Run_Table-1a1a1a?style=for-the-badge&logo=data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCAyNCAyNCI+PHBhdGggZmlsbD0id2hpdGUiIGQ9Ik0xMiAyQzYuNDggMiAyIDYuNDggMiAxMnM0LjQ4IDEwIDEwIDEwIDEwLTQuNDggMTAtMTBTMTcuNTIgMiAxMiAyem0wIDE4Yy00LjQxIDAtOC0zLjU5LTgtOHMzLjU5LTggOC04IDggMy41OSA4IDgtMy41OSA4LTggOHptMC0xNGMtMy4zMSAwLTYgMi42OS02IDZzMi42OSA2IDYgNiA2LTIuNjkgNi02LTIuNjktNi02LTZ6Ii8+PC9zdmc+" alt="CoC 7th" />
  <br/>
  <img src="https://img.shields.io/badge/Next.js-16-black?logo=nextdotjs" alt="Next.js" />
  <img src="https://img.shields.io/badge/FastAPI-0.115-009688?logo=fastapi&logoColor=white" alt="FastAPI" />
  <img src="https://img.shields.io/badge/TypeScript-5-3178c6?logo=typescript&logoColor=white" alt="TypeScript" />
  <img src="https://img.shields.io/badge/WebRTC-voice-333?logo=webrtc" alt="WebRTC" />
  <img src="https://img.shields.io/badge/license-MIT-green" alt="License" />
</p>

# CoC Yes - 在线克苏鲁的呼唤跑团助手

一个专为 **Call of Cthulhu 7th Edition** 桌游跑团打造的在线协作空间。
把房间、语音、角色卡、骰子、KP 管理和规则书检索整合成一个即开即用的 Web 工作台。

### 功能特性

| 功能 | 说明 |
|---|---|
| 房间管理 | 一键创建跑团房间，邀请码加入，成员权限控制（KP / 玩家 / 旁观） |
| 实时聊天 | WebSocket 驱动的文字聊天，支持 @提及、私聊、引用回复 |
| 实时语音 | WebRTC 网状对等语音通话，KP 全员静音/强制静音/踢出 |
| 骰子研究所 | 后端结算、防作弊，d100 检定、奖励/惩罚骰、对抗、疗伤、精神检定、武器故障 |
| 角色卡 | 上传 Excel 角色卡自动解析，从属性/技能一键发起检定 |
| KP 控制台 | 暗骰、编辑角色卡、结束会话并生成总结报告 |
| 界面主题 | 默认纯黑背景，支持深灰、墨绿、深蓝、暗红等多种纯色主题切换 |
| 规则书检索 | 本地 PDF 全文检索，准确引用页码和来源 |
| 录音消息 | 录制并发送语音消息，支持播放与进度控制 |

## 技术栈

| 层 | 技术 |
|---|---|
| 前端 | Next.js 16 (Turbopack) + TypeScript |
| 后端 | FastAPI + Python 3.10+ |
| 语音 | WebRTC (mesh topology) + WebSocket signaling |
| 数据 | 本地 JSON 持久化（可替换为 PostgreSQL） |

## 项目结构

```
coc-yes/
  apps/
    web/            # Next.js 前端
      src/
        components/ # React 组件（房间、骰子、角色卡、语音、录音）
        pages/      # 页面路由
        hooks/      # 自定义 Hooks
    api/            # FastAPI 后端
      app/modules/
        rooms/      # 房间、聊天、语音信令
        dice/       # 骰子结算引擎
        characters/ # 角色卡解析与编辑
        rules/      # 规则书 PDF 检索
  packages/
    shared/         # 前后端共享类型和 COC 常量
  scripts/
    dev.mjs         # 并发启动脚本
  start.bat         # Windows 一键启动
```

## 本地启动

### 方式一：一键启动（推荐）

双击项目根目录的 `start.bat`，脚本会自动完成：
1. 检查 Node.js 和 Python 环境
2. 自动生成 `.env` 配置文件
3. 自动安装缺失的依赖
4. 同时启动前后端服务

```powershell
.\start.bat
```

### 方式二：命令行启动

```powershell
npm install
python -m venv appspi\.venv
appspi\.venv\Scripts\python.exe -m pip install -r appspiequirements.txt
copy .env.example appspi\.env
copy .env.example apps\web\.env.local
npm run dev
```

启动后访问：
- 前端页面：http://localhost:3000
- 后端 API：http://127.0.0.1:8000/api/health
- API 文档：http://127.0.0.1:8000/docs

## API 接口速览

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/api/rooms` | 创建房间 |
| POST | `/api/rooms/join` | 邀请码加入房间 |
| GET | `/api/rooms/{id}` | 获取房间详情 |
| POST | `/api/rooms/{id}/messages` | 发送消息 |
| POST | `/api/rooms/{id}/rolls` | 投掷骰子 |
| POST | `/api/rooms/{id}/characters/upload` | 上传角色卡 |
| PUT | `/api/rooms/{id}/characters/{cid}` | KP 编辑角色卡 |
| POST | `/api/rooms/{id}/voice` | 上传语音消息 |
| POST | `/api/rooms/{id}/activate` | KP 激活房间 |
| POST | `/api/rooms/{id}/end` | KP 结束房间 |
| GET | `/api/rooms/{id}/summary` | 获取会话总结 |
| GET | `/api/rules/search?q=关键词` | 规则书检索 |
| WS | `/api/rooms/{id}/ws?member_id=...` | 房间实时推送 |

## 重要约定

- 不提交本地规则书 PDF、上传文件、规则索引和录音文件
- 骰子结果必须由后端生成并写入日志
- 规则查询必须基于本地授权 PDF 检索，回答带来源和页码
- 每完成一个大模块，及时提交并推送
