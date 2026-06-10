# 在线 COC 跑团助手架构方案

## 1. 项目定位

这是一个面向 COC 跑团的在线协作工作台，而不是单纯的骰子工具或规则查询器。

核心目标：

- 支持 KP 与玩家在同一房间内进行文字、语音、录音与会后总结。
- 支持上传角色卡后自动解析属性、技能、武器、装备、背景故事与调查员经历。
- 支持 KP 查看、修改、锁定或备注玩家角色卡。
- 支持常见 COC 骰子与属性/技能快捷检定，并记录可追溯的投掷日志。
- 支持快速查询 COC 规则书，答案必须基于本地授权资料，并带页码或出处。

重要边界：

- 不建议内置整本规则书文本作为公开资源。
- 规则查询应使用用户本地提供的正版 PDF 或授权资料做索引。
- 规则回答不能依赖模型记忆，必须基于检索结果。

## 2. 推荐技术栈

### 前端

推荐：`Next.js + React + TypeScript`

用途：

- 房间大厅、跑团桌面、KP 控制台。
- 聊天窗口、语音状态、录音控制。
- 角色卡展示与编辑。
- 骰子面板与投掷日志。
- 规则书检索 UI。

选择理由：

- 适合复杂交互型 Web 产品。
- TypeScript 有利于管理角色卡、骰子、规则片段等结构化数据。
- 后续可以比较自然地扩展成桌面端或 PWA。

### 后端

推荐：`FastAPI + Python`

用途：

- 用户、房间、角色卡、规则检索、投掷日志、录音文件管理。
- Excel 角色卡解析。
- PDF 规则书解析与检索索引生成。
- 跑团结束后的聊天记录、录音转写与总结。

选择理由：

- Python 处理 PDF、Excel、文本检索、语音转写和 AI 总结更顺手。
- FastAPI 对 WebSocket、文件上传、异步任务支持较好。
- 后续接向量检索、OCR、语音识别都更方便。

### 实时通信

文字聊天与状态同步：`WebSocket`

语音通话：`LiveKit / WebRTC`

推荐路线：

- MVP 阶段：先实现文字聊天、录音上传、语音留言。
- 正式在线语音阶段：接入 LiveKit，处理多人语音房间、静音、成员状态、录音。

原因：

- 纯手写 WebRTC 多人语音复杂度较高，尤其涉及 NAT、TURN、录制和断线重连。
- LiveKit 可以把多人语音、房间、轨道、录制能力交给成熟基础设施。

### 数据库

推荐：`PostgreSQL`

用途：

- 用户、房间、成员、角色卡、聊天消息、投掷日志、规则索引元数据。

开发阶段可选：

- 早期原型可用 `SQLite`。
- 一旦进入多人在线与长期房间存档，应切到 `PostgreSQL`。

### 文件存储

开发阶段：

- 本地 `uploads/`

正式部署：

- `S3 / MinIO / 阿里云 OSS / 腾讯云 COS`

存储内容：

- 用户上传的角色卡 Excel。
- 规则书 PDF。
- 录音文件。
- 语音转写文本。

## 3. 推荐项目结构

```text
coc-assistant/
  apps/
    web/
      src/
        app/
        components/
        features/
          room/
          chat/
          voice/
          dice/
          character/
          rules/
          keeper/
        lib/
        styles/

    api/
      app/
        main.py
        core/
          config.py
          security.py
        modules/
          auth/
          rooms/
          chat/
          voice/
          dice/
          characters/
          rules/
          summaries/
        workers/
          transcribe_worker.py
          summary_worker.py
          rules_index_worker.py
        storage/
          files.py
        db/
          models.py
          migrations/

  packages/
    shared/
      types/
      dice/
      coc/

  data/
    rules/
      source/
      indexes/
    uploads/

  docs/
    architecture.md
    api.md
    database.md
    mvp-roadmap.md
```

说明：

- `apps/web` 放前端。
- `apps/api` 放后端。
- `packages/shared` 放前后端共享的骰子表达式、COC 常量、数据类型定义。
- `data/rules/source` 放用户本地提供的正版规则书 PDF。
- `data/rules/indexes` 放生成后的规则检索索引。

## 4. 核心模块划分

### 房间模块

负责：

- 创建跑团房间。
- KP 邀请玩家。
- 管理玩家在线状态。
- 管理房间阶段：准备中、进行中、已结束。

### 聊天模块

负责：

- 文字消息。
- 系统消息。
- 骰子结果消息。
- KP 私密备注。
- 录音消息。

消息类型建议：

```text
text
dice_roll
voice_clip
system
keeper_note
character_update
rule_reference
```

### 语音与录音模块

MVP 阶段：

- 浏览器录音。
- 上传录音文件。
- 在聊天中播放录音。
- 跑团结束后汇总录音与文字聊天。

正式阶段：

- LiveKit 多人语音房间。
- 服务端录制。
- 录音转写。
- 会后自动总结。

### 骰子模块

负责：

- 通用表达式：`1d100`、`1d6`、`2d6+3`。
- COC 快捷检定：普通、困难、极难、大成功、大失败。
- 奖励骰、惩罚骰。
- 属性/技能一键投掷。
- 投掷记录不可被普通玩家修改。

原则：

- 骰子必须由后端生成结果。
- 前端只负责发起请求和展示。
- 每次投掷都写入日志。

### 角色卡模块

负责：

- 上传 Excel 角色卡。
- 自动解析基础信息、属性、技能、武器、装备、资产、背景故事、调查员经历。
- 生成结构化角色卡 JSON。
- 前端展示为可检定面板。
- KP 可以查看、修改、备注、锁定字段。

解析策略：

- 优先读取模板中的命名区域，例如 `STR`、`DEX`、`POW`、`CON`、`APP`、`EDU`、`SIZ`、`INT`、`Luck`。
- 对姓名、玩家、职业、年龄、性别、住地、故乡等字段使用固定区域映射。
- 对背景故事、形象描述、思想与信念、重要之人、调查员经历等长文本使用模板标签映射。
- 对自定义字段使用“标签邻近值”兜底解析。
- 解析结果允许 KP 手动修正。

### 规则书模块

负责：

- 导入本地正版 PDF。
- 建立页码级文本索引。
- 支持关键词检索。
- 支持规则问答，但回答必须引用检索片段。

准确性原则：

- 没有检索依据时不回答。
- 每条规则回答都显示来源页码。
- 可以展示短摘录，但不建议公开暴露整本规则书全文。
- 如果后续接 AI，总结时也必须走 RAG，不允许裸模型回答规则。

### 总结模块

负责：

- 跑团结束后整理聊天记录。
- 汇总骰子关键事件。
- 汇总角色卡变化。
- 汇总录音转写。
- 输出本次跑团摘要、未解决线索、NPC、玩家待办、下一次开团提醒。

## 5. 核心数据库表

### users

```text
id
display_name
email
password_hash
role
created_at
```

### rooms

```text
id
name
keeper_id
status
created_at
ended_at
```

### room_members

```text
id
room_id
user_id
role
joined_at
```

### characters

```text
id
room_id
owner_id
name
source_file_id
data_json
keeper_notes
locked_fields_json
created_at
updated_at
```

### chat_messages

```text
id
room_id
sender_id
message_type
content_json
created_at
```

### dice_rolls

```text
id
room_id
character_id
roller_id
expression
target_name
target_value
difficulty
result_json
created_at
```

### rule_sources

```text
id
title
file_id
edition
language
created_at
```

### rule_chunks

```text
id
source_id
page
text
keywords
embedding
created_at
```

### recordings

```text
id
room_id
uploader_id
file_id
duration_seconds
transcript_text
created_at
```

### session_summaries

```text
id
room_id
summary_text
highlights_json
open_threads_json
created_at
```

## 6. 第一阶段 MVP 范围

第一阶段先做这些：

- 创建房间。
- 本地或简单账号登录。
- 文字聊天。
- 浏览器录音并上传为语音消息。
- 角色卡 Excel 上传与自动解析。
- KP 查看与修改角色卡。
- 常见骰子与属性/技能快捷投掷。
- 投掷结果广播到房间聊天。
- 本地规则 PDF 检索，结果带页码。
- 跑团结束后生成文本总结草稿。

第一阶段暂不做：

- 完整实时多人语音。
- 复杂权限系统。
- 商业级部署。
- 移动端深度优化。
- 完整 OCR。
- 多规则书版本管理。

## 7. 第二阶段增强

- 接入 LiveKit 实时语音。
- 服务端录音与自动转写。
- 规则检索接向量库。
- 角色卡版本历史。
- KP 暗骰、私密消息、秘密线索投递。
- 地图、手out、NPC 卡片。
- 跑团战役归档。
- 玩家个人角色库。

## 8. 需要尽早确认的技术决策

- 是否必须支持公网多人在线，还是先局域网/本机原型。
- 是否需要账号系统，还是第一版用房间邀请码。
- 语音是必须实时通话，还是第一版接受录音留言。
- 规则书是否只支持用户本地上传的正版 PDF。
- 是否允许接入 AI 服务做转写和总结。
- 角色卡是否只支持当前这份 Excel 模板，还是要支持多模板。

## 9. 推荐结论

推荐路线：

```text
Next.js 前端
FastAPI 后端
PostgreSQL 数据库
WebSocket 实时文字与状态同步
LiveKit 作为正式语音方案
本地 PDF 页码级规则索引
Excel 角色卡解析后结构化存储
```

这个架构能同时覆盖在线跑团、角色卡解析、KP 管理、骰子可信记录和规则准确检索，并且每个模块都可以分阶段实现。
