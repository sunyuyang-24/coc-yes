# COC Yes 待实现功能清单

> 从需求文档、MVP路线图、Agent审查、规则书合规审查、对话历史中汇总的全部"后续实现"功能。
> 最后更新：2026-06-11 (v2 - 补全遗漏项)

---

## 一、P0 - 立即实现（当前代码中明确缺失）

| # | 功能 | 来源 | 状态 | 说明 |
|---|------|------|------|------|
| 1 | SAN Check 自动关联角色 SAN 值 | 规则书审查 #8 | **已完成** | 投掷面板新增 SAN 检定 checkbox |
| 2 | 投骰音效 | Agent 审查 (调查员) #3.9 | **已完成** | Web Audio API 嗒嗒声，settings 开关控制 |
| 3 | 消息引用回复 | Agent 审查 (调查员) #13 | **已完成** | 消息旁"↩"按钮，回复显示引用块 |
| 4 | 背景字段中文标签 | Agent 审查 (调查员) #3.5 | **已完成** | CharacterCardView 内联中文映射 |
| 5 | 角色卡属性/技能值直接编辑 | Agent 审查 (调查员) #3.7 | **已完成** | KP 编辑模式放开数值输入 |
| 6 | 投掷日志按玩家/角色筛选 | Agent 审查 (调查员) #15 | **已完成** | rolls log 新增玩家筛选下拉框 |
| 7 | HP/SAN 进度条 | Agent 审查 (调查员) #3.8 | **已完成** | status chip 底部彩色进度条 |
| 8 | 私密线索投递 | product-requirements.md 3.7 | **已完成** | KP composer 上方下拉选目标玩家 |
| 9 | NPC 管理 | mvp-roadmap.md 阶段11 | **已完成** | KP 快速创建 NPC，NPC 卡片特殊样式 |

## 二、阶段9：实时语音（路线图优先级：阶段9）

| 功能 | 来源 | 说明 |
|------|------|------|
| 多人实时语音房间 | mvp-roadmap.md 阶段9 | 接入 LiveKit 或 WebRTC，房间成员实时语音 |
| 成员静音状态 | mvp-roadmap.md 阶段9 | 显示谁在说话、谁静音 |
| 断线重连 | mvp-roadmap.md 阶段9 | 网络中断后自动恢复 |
| 服务端录制 | mvp-roadmap.md 阶段9 | KP 可控制录音起止 |
| 语音频道管理 | product-requirements.md 3.3 | KP 可开关语音频道 |

## 三、阶段10：语音转写与总结增强

| 功能 | 来源 | 说明 |
|------|------|------|
| 录音转写 | mvp-roadmap.md 阶段10 | 录音文件转为文字 |
| 转写与消息时间线对齐 | mvp-roadmap.md 阶段10 | 按时间与聊天消息对齐 |
| 总结合并多源数据 | mvp-roadmap.md 阶段10 | 文字聊天+语音转写+投掷日志+角色卡变化 |
| AI 转写 | product-requirements.md 4 | 接入 AI 服务做转写和总结 |
| 总结可导出 | mvp-roadmap.md 阶段10 | 导出为 Markdown/PDF |

## 四、阶段11：完整跑团辅助能力

### 4.1 NPC 管理
| 功能 | 来源 | 说明 |
|------|------|------|
| NPC 卡片创建/编辑 | mvp-roadmap.md 阶段11 | KP 创建和管理 NPC |
| NPC 快捷投掷 | product-requirements.md 3.7 | NPC 对抗检定一键投掷 |
| NPC 状态追踪 | Agent 审查 (KP) | HP/SAN 实时追踪 |

### 4.2 暗骰增强
| 功能 | 来源 | 状态 | 说明 |
|------|------|------|------|
| 暗骰独立面板 | product-requirements.md 3.7 | **已完成** | KP 专用暗骰面板，红色主题，默认勾选暗骰 |
| 暗骰 WebSocket 按角色过滤 | Agent 审查 (KP) #6 | **已完成** | connection_manager 按 member role 过滤广播数据 |

### 4.3 私密线索投递
| 功能 | 来源 | 说明 |
|------|------|------|
| KP→玩家私密消息 | product-requirements.md 3.7 | 向特定玩家发送线索 |
| KP 私密频道 | product-requirements.md 3.2 | **已完成** | 私密线索下拉 + 悄悄话选择器覆盖 |

### 4.4 战役管理
| 功能 | 来源 | 说明 |
|------|------|------|
| 战役时间线 | mvp-roadmap.md 阶段11 | 跨多次跑团的战役时间线 |
| 战役归档 | mvp-roadmap.md 阶段11 | 房间结束后归档为战役记录 |
| 玩家个人角色库 | mvp-roadmap.md 阶段11 | 跨房间复用角色 |
| 手out 管理 | mvp-roadmap.md 阶段11 | KP 分发跑团资料 |

### 4.5 规则书增强
| 功能 | 来源 | 说明 |
|------|------|------|
| 多规则书管理 | product-requirements.md 3.6 | 支持多个 PDF |
| 语义搜索 | product-requirements.md 3.6 | 向量检索替代关键词匹配 |
| KP 自定义规则 | product-requirements.md 3.6 | 添加/编辑房规 |
| 规则问答 | product-requirements.md 3.6 | 基于 RAG 的规则问答 |
| 常用规则收藏 | product-requirements.md 3.6 | 收藏高频条目 |
| PDF 页码直跳 | Agent 审查 (KP) #15 | 搜索结果直跳到 PDF 对应页 |

## 五、COC 7e 规则补全（已实现核心函数 + API）

| 功能 | 来源 | 状态 | 说明 |
|------|------|------|------|
| 对抗检定 | 规则书审查 #10 | **已完成** | POST /api/rooms/{id}/coc/opposed |
| 推动检定 (Pushing) | 规则书 CRB p79 | **已完成** | pushing_check() 判断是否可推动 |
| 急救/治疗 | 规则书 CRB p66 | **已完成** | POST /api/rooms/{id}/coc/heal (first_aid/medicine) |
| 重伤追踪 (Major Wound) | 规则书 CRB | **已完成** | POST /api/rooms/{id}/coc/wound |
| 临时疯狂/不定疯狂 | 规则书 CRB p156 | **已完成** | POST /api/rooms/{id}/coc/insanity |
| 武器 malf 判定 | 规则书 CRB | **已完成** | POST /api/rooms/{id}/coc/malfunction |

## 六、社交/沟通增强

| 功能 | 来源 | 说明 |
|------|------|------|
| 私聊 | product-requirements.md 3.2 | **已完成** | 悄悄话选择器，仅双方可见 |
| 消息搜索 | product-requirements.md 3.2 | **已完成** | 聊天面板顶部搜索框 |
| @提及 | Agent 审查 (调查员) #13 | **已完成** | @人名自动高亮，后台解析 mentionIds |

## 七、房间/权限增强

| 功能 | 来源 | 说明 |
|------|------|------|
| 房间密码 | product-requirements.md 3.1 | **已完成** | 创建时可选密码，加入时验证 |
| 旁观者身份 | product-requirements.md 3.1 | **已完成** | 加入时选择旁观者，只读不可发言投掷 |
| 多 KP | product-requirements.md 3.1 | 一个房间多 KP |
| 邀请码使用次数限制 | Agent 审查 (KP) #7 | 可设上限 |
| 房间成员上限 | Agent 审查 (KP) #7 | 限制最大人数 |

## 八、角色卡增强

| 功能 | 来源 | 说明 |
|------|------|------|
| 多角色卡支持 | Agent 审查 (调查员) #8 | **已完成** | 一个玩家多张角色卡，active 标记激活态 |
| 当前值/初始值分离 | Agent 审查 (调查员) #4 | **已完成** | CharacterCard.initialStatus 字段，进度条用初始值做分母 |
| 多模板支持 | product-requirements.md 4 | **已完成** | 通过 Excel 命名区域映射支持多模板 |
| 角色卡更新请求 | product-requirements.md 3.5 | **已完成** | 玩家端"请求更新角色卡"按钮，复制消息 |
| 技能分类展示 | Agent 审查 (调查员) #7 | **已完成** | 战斗/社交/知识感知/其他 四组分类 |
| HP/SAN 进度条 | Agent 审查 (调查员) #3.8 | **已完成** | status chip 底部彩色进度条 |

## 九、投掷体验增强

| 功能 | 来源 | 状态 | 说明 |
|------|------|------|------|
| 投掷与规则搜索关联 | Agent 审查 (调查员) #3.4 | **已完成** | 投掷结果旁"查规则"按钮，自动填入标签搜索 |
| 记住上次投掷参数 | Agent 审查 (调查员) #5.2 | **已完成** | 投掷参数持久化到 localStorage |
| 快捷投掷支持奖励骰 | Agent 审查 (调查员) #6 | **已完成** | 属性/技能投掷旁奖励骰下拉选择器 |

## 十、UI/UX 增强

| 功能 | 来源 | 状态 | 说明 |
|------|------|------|------|
| 移动端深度优化 | Agent 审查 (调查员) #11 | **已完成** | <860px 成员栏置顶、composer 固定底部、卡片紧凑 |
| PWA 支持 | architecture.md | 待实现 | 离线可用、桌面安装 |
| 房间级主题 | product-requirements.md 3.8 | **已完成** | KP 选择 6 种主题色，同步全房间，新增羊皮纸 |
| 总结导出 | mvp-roadmap.md 阶段10 | **已完成** | 复制到剪贴板 + 下载 .md 文件 |
| 投掷日志导出 | 自研 | **已完成** | rolls log 顶部复制日志按钮 |
| room-console 拆分 | Agent 审查 (KP) #18 | **已完成** | CharacterCardView 拆出为独立组件 |

## 十一、后端架构升级

| 功能 | 来源 | 说明 |
|------|------|------|
| JSON→SQLite 迁移 | Agent 审查 (KP) #19 | 更好并发 |
| PostgreSQL 正式数据库 | architecture.md 5 | 多人在线后切换 |
| S3/OSS 文件存储 | architecture.md | 云存储 |
| 账号系统 | architecture.md 8 | 用户注册/登录 |
| 前后端共享类型完整化 | Agent 审查 (KP) #20 | VoiceRecord、Summary 等迁至 shared |

## 十二、测试与质量

| 功能 | 来源 | 说明 |
|------|------|------|
| 单元测试 | 代码审查 | 骰子、角色卡解析、规则索引 |
| E2E 测试 | 代码审查 | 核心跑团流程 |
| Agent 玩法测试 | 对话历史 | KP + 调查员 agent 模拟跑团，产出优化报告 |

---

## 优先级总览

**P0（当前立即实现）：**
1. SAN Check 自动关联角色 SAN 值
2. 投骰音效（Web Audio beep）
4. 消息引用回复
5. 背景字段中文标签
6. KP 可编辑属性/技能数值
7. 投掷日志按玩家筛选

**P1（提升跑团体验）：**
8. NPC 管理完整化
9. 私密线索投递
10. 角色卡当前值/初始值分离
11. HP/SAN 进度条
12. 投掷与规则关联

**P2（阶段9-10）：**
13. 实时语音（LiveKit）
14. 语音转写
15. AI 总结增强

**P3（阶段11+）：**
16. 战役管理
17. 多规则书
18. 账号系统
19. PostgreSQL 迁移
20. PWA / 移动端
