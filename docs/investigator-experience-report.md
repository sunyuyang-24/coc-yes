# COC Yes 调查员体验需求报告

**调查员**: 哈罗德·布莱克伍德（Harold Blackwood），42岁，古董商
**评估日期**: 2026-06-11
**评估范围**: 加入房间 -> 上传角色卡 -> 查看属性/技能 -> 参与聊天 -> 进行检定 -> 搜索规则书 -> 录制语音消息 -> 查看总结

---

## 1. 操作流程走查

| 步骤 | 操作 | 代码入口 | 流畅度 | 备注 |
|------|------|----------|--------|------|
| 加入房间 | 输入邀请码+昵称 | room-console.tsx joinRoom() | 顺畅 | 有 localStorage 恢复，体验不错 |
| 上传角色卡 | 选择 xlsx 文件上传 | room-console.tsx 上传逻辑 | 顺畅 | 后端解析逻辑完整 |
| 查看属性 | 展开角色卡面板 | room-console.tsx CharacterCardView | 良好 | 属性、技能、武器、法术、背景、经历都在 |
| 参与聊天 | 输入文字并发送 | room-console.tsx sendMessage() | 顺畅 | WebSocket 实时同步 |
| 进行检定 | 属性/技能一键投掷 | room-console.tsx rollCharacterCheck() | 直观 | 自动带角色名+字段名+目标值 |
| 自由投掷 | 手动输入表达式 | room-console.tsx rollDice() | 良好 | 支持奖励骰/惩罚骰 |
| 规则书搜索 | 输入关键词查询 | rules-search-panel.tsx | 良好 | 有 PDF 索引状态检查 |
| 录制语音 | 浏览器录音上传 | voice-recorder.tsx | 基本可用 | 支持时长限制设置 |
| 查看总结 | 结束房间后生成 | summary-panel.tsx | 良好 | KP 可编辑草稿 |

---

## 2. 功能优势分析——哪些做得好

### 2.1 角色卡解析深度超出预期
后端 parser.py 对 Excel 的解析覆盖了 9 大属性、HP/SAN/MP/MOV 状态、技能表（左右双列扫描 row 16-50）、武器表、法术表、背景故事（外貌/思想/重要之人/重要之地/珍贵之物/特质/伤痕/恐惧症）、调查员经历（row 97-112），甚至还有 defined_names 回退方案。这意味着即使是手填的非标准模板也有机会解析成功。

### 2.2 COC 7版检定逻辑严谨
roller.py 的 _classify_coc_success 完整实现了：
- 大成功（出目=1）
- 大失败（技能>=50时 96-100；技能<50时 97-100）
- 极难成功（<= 目标值/5）
- 困难成功（<= 目标值/2）
- 普通成功 / 失败

奖励骰/惩罚骰的十位数逻辑在 _roll_coc_d100 中也正确实现。

### 2.3 投掷结果可视化清晰
DiceRollView 对 COC d100 展示十位骰 [tens] 和个位骰 [ones]，让调查员能复核每个骰子的数值，这在跑团中极为重要——玩家需要"看到"骰子。

### 2.4 规则书索引基于本地 PDF
indexer.py 使用 PyMuPDF 提取全页文本并建立页码级索引，搜索结果带来源文件和页码。这保证了规则引用的可追溯性，不会像 LLM 那样凭空编造规则。

### 2.5 会话持久化
localStorage 保存 roomId + memberId，刷新页面后自动恢复房间连接。VoiceRecorder 也通过 loadSettings() 读取用户偏好。这种"不丢进度的安全感"对跑团至关重要。

### 2.6 背景色系统
globals.css 使用 CSS 变量 + data-background 属性实现纯色主题切换（纯黑/深灰/墨绿/深蓝/暗红），每用户独立 localStorage 存储。暗色系对长时间跑团的护眼体验很好。

---

## 3. 功能缺失与体验问题

### 3.1 [P0] 角色卡上传后无法立即看到新角色卡的名字反馈
**位置**: room-console.tsx 上传成功后 setNotice("角色卡已上传")，但 room 状态尚未通过 WebSocket 更新，角色卡列表需要等服务器广播才能刷新。
**建议**: 上传成功后立即乐观更新本地 room.characters，或在 notice 中显示解析出的角色名。

### 3.2 [P0] 属性/技能的半值和五分之一值未在角色卡上展示
**位置**: shared/src/index.ts CharacterAttribute/CharacterSkill 类型定义了 half 和 fifth，后端 parser.py 也计算了 value//2 和 value//5，但前端 CharacterCardView 仅显示属性值和"投掷"按钮，完全没有展示半值和五分之一值。
这在 COC 7版中是核心——KP 经常要求"困难成功"或"极难成功"，玩家需要知道自己技能对应的困难/极难阈值，而不是每次都心算。
**建议**: 属性 chip 中展示格式改为 `STR 45 (22/9)` 或在悬停 tooltip 中展示。

### 3.3 [P1] 技能列表默认只显示前 12 个有值技能
**位置**: room-console.tsx 内 CharacterCardView visibleSkills 逻辑。
```typescript
// 默认只显示前 12 个有值技能
if (!showAllSkills && !skillSearch) filtered = filtered.slice(0, 12);
```
哈罗德作为 75 EDU 的资深古董商，技能远不止 12 个。每次打开角色卡都要点"显示更多"才能看到完整列表。
**建议**: 桌面端默认显示全部技能，或调高阈值到 24。

### 3.4 [P1] 规则书搜索结果无法在角色卡检定时自动关联
投掷检定和规则搜索是两个独立面板，没有任何关联。当玩家投了"神秘学 45"后想知道神秘学规则时，需要手动切换到规则搜索面板、手动输入"神秘学"。
**建议**: 在投掷结果的 DiceRollView 中增加"搜索相关规则"快捷按钮。

### 3.5 [P1] 角色卡背景字段使用英文 key 展示
**位置**: room-console.tsx CharacterCardView 背景展示区域，标签显示 `appearance`、`ideology`、`significantPeople` 等英文 key，而非"外貌描述""思想与信念""重要之人"等中文标签。
**建议**: 增加 BACKGROUND_LABELS 映射（类似 parser.py 中的 ATTRIBUTE_LABELS），在 shared 层做翻译。

### 3.6 [P2] 语音消息无转写文本
录音上传后仅在聊天中出现播放按钮，其他玩家无法快速浏览语音内容。对跑团复盘或快速翻看历史记录非常不便。
**建议**: 短期内增加"转写中..."占位符。

### 3.7 [P2] 角色卡编辑能力受限
KP 编辑模式下只能修改 name/occupation/age/gender 四个基本字段和 keeperNotes，不能直接修改属性值和技能值。如果 Excel 上传后有解析错误，KP 无法补救。
**建议**: 编辑模式下允许修改属性数值和技能数值。

### 3.8 [P2] 缺少"当前血量/最大血量"比例展示
角色卡展示了 HP、SAN、MP 等当前状态，但没有显示这些值相对于最大值的比例。HP 只是一个孤立的数字，玩家无法一眼看出血量剩余比例。
**建议**: HP/SAN/MP 的 status chip 增加进度条或百分比展示。

### 3.9 [P3] 设置面板中投骰音效标注为"待实现"
settings-panel.tsx 中 diceSound checkbox 标注"待实现"，让产品有半成品感。
**建议**: 隐藏选项或实现简单 Web Audio 方案。

### 3.10 [P3] BackgroundPicker 与 SettingsPanel 重复
background-picker.tsx 使用 `coc-yes.background` 作为 storage key，settings-panel.tsx 使用 `coc-yes.settings`。BackgroundPicker 未被 page.tsx 引用，造成代码冗余。
**建议**: 删除 background-picker.tsx。

---

## 4. 角色卡展示完整性评估

| 区块 | 展示内容 | 完整性 | 问题 |
|------|----------|--------|------|
| 基本信息 | 姓名/职业/年龄/性别/时代/住地/故乡 | 完整 | 空字段显示"未填写" |
| 属性 | 9 项属性值 + 投掷按钮 | 良 | **缺少半值和五分之一值** |
| 状态 | HP/SAN/MP/MOV/DB/Build/Armor | 良 | **无最大值比例对比** |
| 技能 | 全技能列表 + 搜索 + 投掷 | 良 | **默认截断 12 个** |
| 武器 | 名称/伤害/技能 + 投掷 | 完整 | 武器关联技能投掷正确 |
| 法术 | 名称/消耗 | 完整 | - |
| 背景 | 8 项背景字段 | 良 | **标签显示英文 key** |
| 经历 | 折叠展示 | 完整 | - |
| KP 备注 | 仅 KP 可见 | 完整 | - |
| 警告 | 解析警告提示 | 完整 | 空模板有明确提示 |

---

## 5. 投掷体验评估

### 5.1 优点
- 属性/技能一键投掷，点名式展示"哈罗德 · 侦查"，代入感强
- COC 7版成功等级判定完整且正确
- 奖励骰/惩罚骰有十位骰可视化
- 暗骰功能对 KP 友好
- 投掷日志可按时间倒序浏览最近 50 条

### 5.2 不足
- 投掷后没有音效：跑团仪式感缺失（P3）
- 投掷结果与规则搜索割裂（见 3.4）
- 自由投掷预设值固定为 60：targetValue 每次手动改，建议记住上次输入值

---

## 6. 优化建议按优先级排序

| 优先级 | 编号 | 问题 | 建议 | 影响范围 |
|--------|------|------|------|----------|
| **P0** | 3.2 | 角色卡不展示半值/五分之一值 | 属性 chip 格式改为 `STR 45 (22/9)` | 前端 CharacterCardView + shared 类型 |
| **P0** | 3.1 | 上传角色卡无即时反馈 | 乐观更新本地 room.characters | room-console.tsx 上传逻辑 |
| **P1** | 3.5 | 背景字段英文 key 展示 | 增加 BACKGROUND_LABELS 中文映射 | shared 层 + 前端展示 |
| **P1** | 3.3 | 技能列表默认截断 12 个 | 桌面端默认全显示或调高阈值 | room-console.tsx visibleSkills |
| **P1** | 3.4 | 投掷与规则搜索无关联 | 投掷结果卡片增加"查规则"按钮 | room-console.tsx + rules-search-panel.tsx |
| **P2** | 3.8 | 状态值无百分比/进度条 | HP/SAN/MP 加可视化进度条 | 前端 CharacterCardView |
| **P2** | 3.6 | 语音消息无转写 | 增加"转写中"占位符 | voice-recorder.tsx |
| **P2** | 3.7 | KP 无法手动修改属性/技能值 | 编辑模式放开数值输入 | room-console.tsx |
| **P3** | 3.9 | 投骰音效标注"待实现" | 隐藏或实现 Web Audio 方案 | settings-panel.tsx |
| **P3** | 3.10 | BackgroundPicker 冗余 | 删除 background-picker.tsx | 清理死代码 |

---

## 7. 总结

作为哈罗德·布莱克伍德，在 COC Yes 中完成一次模拟跑团后，我的核心感受是：**核心引擎扎实，边缘体验粗糙**。

骰子检定逻辑正确、角色卡解析深度好、WebSocket 同步稳定——这三项是产品的地基，打得很稳。但在"跑团过程中的微时刻"上，比如打开角色卡想快速看一眼自己侦查技能的困难阈值是多少、投了神秘学后想顺手查一下神秘学规则、语音留言后队友想快速浏览说了什么——这些场景现在还做不到足够顺滑。

修复 P0 和 P1 问题后，COC Yes 将从一个"功能正确的工具"升级为一个"沉浸式跑团工作台"。
