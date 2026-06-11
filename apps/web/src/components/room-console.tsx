"use client";

import type { FormEvent } from "react";
import { useEffect, useMemo, useRef, useState } from "react";
import type { CharacterCard, DiceRollResult, RoomDetail } from "@coc-yes/shared";
import { RulesSearchPanel } from "@/components/rules-search-panel";
import { VoiceRecorder } from "@/components/voice-recorder";
import { VoiceMessage } from "@/components/voice-message";
import { SummaryPanel } from "@/components/summary-panel";
import { apiRequest, apiUrl, wsUrl } from "@/lib/api";

type RoomResponse = {
  room: RoomDetail;
  currentMemberId: string;
};

type RoomOnlyResponse = {
  room: RoomDetail;
};

type SocketEvent = {
  type: "room_state" | "room_update";
  room: RoomDetail;
};

const STORAGE_KEY = "coc-yes.current-session";

// ---------------------------------------------------------------------------
// Dice sound effect (Web Audio API)
// ---------------------------------------------------------------------------
let _audioCtx: AudioContext | null = null;
function _getAudioCtx(): AudioContext | null {
  if (_audioCtx) return _audioCtx;
  try { _audioCtx = new AudioContext(); } catch { /* 浏览器不支持 */ }
  return _audioCtx;
}

function playDiceSound() {
  const ctx = _getAudioCtx();
  if (!ctx) return;
  try {
    ctx.resume().then(() => {
      const now = ctx.currentTime;
      // 骰子碰撞音效：短促嗒嗒声
      for (let i = 0; i < 3; i++) {
        const osc = ctx.createOscillator();
        const gain = ctx.createGain();
        osc.type = "triangle";
        osc.frequency.setValueAtTime(800 + Math.random() * 400, now + i * 0.06);
        osc.frequency.exponentialRampToValueAtTime(200, now + i * 0.06 + 0.08);
        gain.gain.setValueAtTime(0.15, now + i * 0.06);
        gain.gain.exponentialRampToValueAtTime(0.001, now + i * 0.06 + 0.1);
        osc.connect(gain);
        gain.connect(ctx.destination);
        osc.start(now + i * 0.06);
        osc.stop(now + i * 0.06 + 0.1);
      }
    });
  } catch { /* ignore */ }
}

export function RoomConsole() {
  const [room, setRoom] = useState<RoomDetail | null>(null);
  const [memberId, setMemberId] = useState<string | null>(null);
  const [roomName, setRoomName] = useState("雾港第一夜");
  const [keeperName, setKeeperName] = useState("KP");
  const [inviteCode, setInviteCode] = useState("");
  const [playerName, setPlayerName] = useState("调查员");
  const [draft, setDraft] = useState("");
  const [rollLabel, setRollLabel] = useState("侦查");
  const [expression, setExpression] = useState("1d100");
  const [targetValue, setTargetValue] = useState("60");
  const [bonusPenalty, setBonusPenalty] = useState("0");
  const [hiddenRoll, setHiddenRoll] = useState(false);
  const [replyTo, setReplyTo] = useState<{ id: string; senderName: string; content: string } | null>(null);
  const [sanQuickRoll, setSanQuickRoll] = useState(false);
  const [characterFile, setCharacterFile] = useState<File | null>(null);
  const [notice, setNotice] = useState("创建或加入房间后，聊天会实时同步。");
  const messageEndRef = useRef<HTMLDivElement | null>(null);

  const currentMember = useMemo(
    () => room?.members.find((member) => member.id === memberId) ?? null,
    [memberId, room?.members]
  );

  useEffect(() => {
    const raw = window.localStorage.getItem(STORAGE_KEY);

    if (!raw) {
      return;
    }

    try {
      const session = JSON.parse(raw) as { roomId: string; memberId: string };

      apiRequest<RoomOnlyResponse>(`/api/rooms/${session.roomId}`)
        .then(({ room: restoredRoom }) => {
          setRoom(restoredRoom);
          setMemberId(session.memberId);
          setNotice("已恢复上次进入的房间。");
        })
        .catch(() => {
          window.localStorage.removeItem(STORAGE_KEY);
        });
    } catch {
      window.localStorage.removeItem(STORAGE_KEY);
    }
  }, []);

  useEffect(() => {
    if (!room || !memberId) {
      return;
    }

    const url = `${wsUrl(`/api/rooms/${room.id}/ws`)}?member_id=${encodeURIComponent(memberId)}`;
    const socket = new WebSocket(url);

    socket.onmessage = (event) => {
      const payload = JSON.parse(event.data) as SocketEvent;

      if (payload.type === "room_state" || payload.type === "room_update") {
        setRoom(payload.room);
      }
    };

    socket.onopen = () => setNotice("实时连接已建立。");
    socket.onclose = () => setNotice("实时连接已断开，刷新页面可重连。");
    socket.onerror = () => setNotice("实时连接出现错误，请确认后端服务仍在运行。");

    return () => {
      socket.close();
    };
  }, [memberId, room?.id]);

  useEffect(() => {
    messageEndRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [room?.messages.length]);

  async function createRoom(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setNotice("正在创建房间...");

    const response = await apiRequest<RoomResponse>("/api/rooms", {
      method: "POST",
      body: JSON.stringify({
        name: roomName,
        keeperName
      })
    });

    enterRoom(response.room, response.currentMemberId);
    setNotice("房间已创建，邀请码可以发给玩家。");
  }

  async function joinRoom(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setNotice("正在加入房间...");

    const response = await apiRequest<RoomResponse>("/api/rooms/join", {
      method: "POST",
      body: JSON.stringify({
        inviteCode,
        displayName: playerName
      })
    });

    enterRoom(response.room, response.currentMemberId);
    setNotice("已加入房间。");
  }

  async function sendMessage(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    if (!room || !memberId || !draft.trim()) {
      return;
    }

    const content = draft.trim();
    setDraft("");

    await apiRequest(`/api/rooms/${room.id}/messages`, {
      method: "POST",
      body: JSON.stringify({
        senderId: memberId,
        content
      })
    });
  }

  async function rollDice(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    if (!room || !memberId) {
      return;
    }

    setNotice("正在投掷骰子...");

    await apiRequest(`/api/rooms/${room.id}/rolls`, {
      method: "POST",
      body: JSON.stringify({
        rollerId: memberId,
        expression,
        label: rollLabel || null,
        targetValue: targetValue ? Number(targetValue) : null,
        bonusPenalty: Number(bonusPenalty),
        hidden: hiddenRoll
      })
    });

    setNotice("投掷完成，结果已写入房间日志。");
  }

  async function rollCharacterCheck(label: string, targetValue: number) {
    if (!room || !memberId) {
      return;
    }

    await apiRequest(`/api/rooms/${room.id}/rolls`, {
      method: "POST",
      body: JSON.stringify({
        rollerId: memberId,
        expression: "1d100",
        label,
        targetValue,
        bonusPenalty: 0
      })
    });

    setNotice(`已发起 ${label} 检定。`);
  }

  async function updateCharacter(
    characterId: string,
    basic: Record<string, string>,
    attributes: Array<{ key: string; value: number | null }>,
    keeperNotes: string
  ) {
    if (!room || !memberId) {
      return;
    }

    await apiRequest(`/api/rooms/${room.id}/characters/${characterId}`, {
      method: "PATCH",
      body: JSON.stringify({
        editorId: memberId,
        basic,
        attributes,
        keeperNotes
      })
    });

    const detail = await apiRequest<RoomOnlyResponse>(`/api/rooms/${room.id}`);
    setRoom(detail.room);
    setNotice("角色卡已保存。");
  }

  async function uploadCharacter(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    if (!room || !memberId || !characterFile) {
      setNotice("请先选择一个 Excel 角色卡文件。");
      return;
    }

    const body = new FormData();
    body.append("ownerId", memberId);
    body.append("file", characterFile);
    setNotice("正在上传并解析角色卡...");

    const response = await fetch(apiUrl(`/api/rooms/${room.id}/characters/upload`), {
      method: "POST",
      body
    });

    if (!response.ok) {
      const errorText = await response.text();
      throw new Error(errorText || `HTTP ${response.status}`);
    }

    const detail = await apiRequest<RoomOnlyResponse>(`/api/rooms/${room.id}`);
    setRoom(detail.room);
    setNotice("角色卡已解析并绑定到房间。");
  }

  function leaveLocalRoom() {
    setRoom(null);
    setMemberId(null);
    window.localStorage.removeItem(STORAGE_KEY);
    setNotice("已离开本地房间视图，房间记录仍保留在后端。");
  }

  function enterRoom(nextRoom: RoomDetail, nextMemberId: string) {
    setRoom(nextRoom);
    setMemberId(nextMemberId);
    window.localStorage.setItem(
      STORAGE_KEY,
      JSON.stringify({
        roomId: nextRoom.id,
        memberId: nextMemberId
      })
    );
  }

  return (
    <section className="room-console" aria-label="房间与文字聊天">
      <div className="room-console__setup">
        <form className="console-card" onSubmit={createRoom}>
          <p className="panel__kicker">Keeper</p>
          <h2>创建跑团房间</h2>
          <label>
            房间名
            <input value={roomName} onChange={(event) => setRoomName(event.target.value)} />
          </label>
          <label>
            KP 名称
            <input value={keeperName} onChange={(event) => setKeeperName(event.target.value)} />
          </label>
          <button className="button button--primary" type="submit">
            创建房间
          </button>
        </form>

        <form className="console-card" onSubmit={joinRoom}>
          <p className="panel__kicker">Investigator</p>
          <h2>加入已有房间</h2>
          <label>
            邀请码
            <input
              value={inviteCode}
              onChange={(event) => setInviteCode(event.target.value.toUpperCase())}
              placeholder="例如 A1B2C3"
            />
          </label>
          <label>
            玩家名称
            <input value={playerName} onChange={(event) => setPlayerName(event.target.value)} />
          </label>
          <button className="button button--ghost" type="submit">
            加入房间
          </button>
        </form>
      </div>

      <div className="notice-line">{notice}</div>

      {room ? (
        <div className="room-board">
          <aside className="member-rail">
            <div>
              <p className="panel__kicker">Room</p>
              <h2>{room.name} <span className={`room-status room-status--${room.status}`}>{room.status === "preparing" ? "准备中" : room.status === "active" ? "进行中" : "已结束"}</span></h2>
              <div className="invite-box">
                <span>邀请码</span>
                <strong>{room.inviteCode}</strong>
              </div>
              {currentMember ? (
                <p className="current-member">
                  当前身份：{currentMember.displayName} · {currentMember.role === "keeper" ? "KP" : "玩家"}
                </p>
              ) : null}
            </div>

            <div className="member-list">
              {room.members.map((member) => (
                <div className="member-item" key={member.id}>
                  <span className={member.online ? "presence presence--online" : "presence"} />
                  <div>
                    <strong>{member.displayName}</strong>
                    <small>{member.role === "keeper" ? "KP" : "玩家"}{(room?.characters || []).find((c) => c.ownerId === member.id) ? " · " + ((room?.characters || []).find((c) => c.ownerId === member.id)?.basic?.name || "角色") : ""}</small>
                  </div>
                </div>
              ))}
            </div>

            <form className="dice-panel" onSubmit={rollDice}>
              <p className="panel__kicker">Dice</p>
              <h3>可信投掷</h3>
              <label>
                标签
                <input value={rollLabel} onChange={(event) => setRollLabel(event.target.value)} />
              </label>
              <label>
                表达式
                <input value={expression} onChange={(event) => setExpression(event.target.value)} />
              </label>
              <div className="dice-panel__row">
                <label>
                  目标值
                  <input
                    inputMode="numeric"
                    value={targetValue}
                    onChange={(event) => setTargetValue(event.target.value)}
                  />
                </label>
                <label>
                  奖惩骰
                  <select value={bonusPenalty} onChange={(event) => setBonusPenalty(event.target.value)}>
                    <option value="2">奖励 2</option>
                    <option value="1">奖励 1</option>
                    <option value="0">无</option>
                    <option value="-1">惩罚 1</option>
                    <option value="-2">惩罚 2</option>
                  </select>
                </label>
              </div>
              <div className="quick-rolls">
                {["1d100", "1d6", "1d10", "2d6+3"].map((item) => (
                  <button key={item} type="button" onClick={() => setExpression(item)}>
                    {item}
                  </button>
                ))}
              </div>
              <div className="dice-panel__checks">
                <label className="dice-panel__check-label">
                  <input type="checkbox" checked={sanQuickRoll} onChange={(e) => setSanQuickRoll(e.target.checked)} />
                  SAN 检定（自动关联角色 SAN）
                </label>
              </div>
              <button className="button button--primary" type="submit">
                后端投掷
              </button>
            </form>

            <form className="upload-panel" onSubmit={uploadCharacter}>
              <p className="panel__kicker">Character</p>
              <h3>上传角色卡</h3>
              <label>
                Excel 文件
                <input
                  accept=".xlsx,.xlsm"
                  onChange={(event) => setCharacterFile(event.target.files?.[0] ?? null)}
                  type="file"
                />
              </label>
              <button className="button button--ghost" type="submit">
                解析并绑定
              </button>
            </form>

            <button className="text-button" type="button" onClick={leaveLocalRoom}>
              仅退出本地视图
            </button>
          </aside>

          <section className="chat-panel">
            <div className="chat-log">
              {room.messages.map((message) => (
                <article className={`chat-message chat-message--${message.type}`} key={message.id}>
                  <div className="chat-message__meta">
                    <strong>{message.senderName}</strong>
                    <span>{formatTime(message.createdAt)}</span>
                  </div>
                  {message.type === "dice_roll" && message.roll ? (
                    <DiceRollView roll={message.roll} />
                  ) : (
                    <p>{message.content}</p>
                  )}
                </article>
              ))}
              <div ref={messageEndRef} />
            </div>

            {replyTo ? (
              <div className="reply-indicator">
                <span>回复 {replyTo.senderName}：{replyTo.content.slice(0, 60)}{replyTo.content.length > 60 ? "..." : ""}</span>
                <button className="text-button" onClick={() => setReplyTo(null)} type="button">取消</button>
              </div>
            ) : null}
            <form className="composer" onSubmit={sendMessage}>
              <input
                value={draft}
                onChange={(event) => setDraft(event.target.value)}
                placeholder={replyTo ? `` : "输入跑团消息、线索或 KP 描述..."}
              />
              <button className="button button--primary" type="submit">
                发送
              </button>
            </form>
          </section>
        </div>
      ) : null}

      {room?.characters?.length ? (
        <section className="character-shelf">
          {room.characters.map((character) => (
            <CharacterCardView
              canEdit={currentMember?.role === "keeper"}
              canRoll={Boolean(currentMember)}
              character={character}
              key={character.id}
              onRoll={rollCharacterCheck}
              onUpdate={updateCharacter}
            />
          ))}
        </section>
      ) : null}

      <section className="rules-shelf">
        <RulesSearchPanel
          showSendToChat
          onSendToChat={(text) => {
            setDraft(text);
          }}
        />
      </section>

      {room?.rolls && room.rolls.length > 0 && (
        <section className="rolls-log">
          <h3>投掷日志 ({room.rolls.length})</h3>
          <div className="rolls-log__list">
            {[...room.rolls].reverse().slice(0, 50).map((roll) => (
              <div key={roll.id} className={`rolls-log__item ${roll.hidden ? "rolls-log__item--hidden" : ""}`}>
                <span className="rolls-log__time">{formatTime(roll.createdAt)}</span>
                <span className="rolls-log__roller">{roll.rollerName}</span>
                <span className="rolls-log__expr">{roll.expression}</span>
                {roll.hidden ? (
                  <span className="rolls-log__result rolls-log__result--hidden">暗骰</span>
                ) : (
                  <span className={`rolls-log__result rolls-log__result--${roll.successLevel || "none"}`}>
                    {roll.total}{roll.successLabel ? ` (${roll.successLabel})` : ""}
                  </span>
                )}
              </div>
            ))}
          </div>
        </section>
      )}

      {room && memberId ? (
        <SummaryPanel
          room={room}
          memberId={memberId}
          isKeeper={currentMember?.role === "keeper"}
        />
      ) : null}

    </section>
  );
}

function DiceRollView({ roll }: { roll: DiceRollResult }) {
  if (roll.hidden) {
    return (
      <div className="dice-roll dice-roll--hidden">
        <p className="dice-roll__expression">[??] ????</p>
      </div>
    );
  }

  const detail = roll.breakdown
    .map((item) => {
      if (item.kind === "coc_d100" && item.tensRolls) {
        return `十位[${item.tensRolls.join(", ")}] 个位[${item.ones}]`;
      }

      const modifier = item.modifier ? ` ${item.modifier > 0 ? "+" : ""}${item.modifier}` : "";
      return `${item.count}d${item.sides}: [${item.rolls.join(", ")}]${modifier}`;
    })
    .join(" · ");

  return (
    <div className="roll-card">
      <div>
        <span>{roll.label || roll.expression}</span>
        <strong>{roll.total}</strong>
      </div>
      {roll.successLabel ? (
        <p className={roll.isSuccess ? "roll-card__success" : "roll-card__fail"}>{roll.successLabel}</p>
      ) : null}
      <small>
        {detail}
        {roll.targetValue ? ` · 目标 ${roll.targetValue}` : ""}
      </small>
    </div>
  );
}

function CharacterCardView({
  canEdit,
  canRoll,
  character,
  onRoll,
  onUpdate
}: {
  canEdit: boolean;
  canRoll: boolean;
  character: CharacterCard;
  onRoll: (label: string, targetValue: number) => Promise<void>;
  onUpdate: (
    characterId: string,
    basic: Record<string, string>,
    attributes: Array<{ key: string; value: number | null }>,
    keeperNotes: string
  ) => Promise<void>;
}) {
  const [skillSearch, setSkillSearch] = useState("");
  const [showAllSkills, setShowAllSkills] = useState(false);
  const visibleSkills = (() => {
    let filtered = skillSearch
      ? character.skills.filter((s) => s.name.toLowerCase().includes(skillSearch.toLowerCase()))
      : character.skills.filter((s) => s.value != null);
    if (!showAllSkills && !skillSearch) filtered = filtered.slice(0, 24);
    return filtered;
  })();
  const name = character.basic.name || character.sourceFileName;
  const [editing, setEditing] = useState(false);
  const [basicDraft, setBasicDraft] = useState({
    name: character.basic.name || "",
    occupation: character.basic.occupation || "",
    age: character.basic.age || "",
    gender: character.basic.gender || ""
  });
  const [attributeDrafts, setAttributeDrafts] = useState<Record<string, string>>(() =>
    Object.fromEntries(character.attributes.map((attribute) => [attribute.key, String(attribute.value ?? "")]))
  );
  const [keeperNotes, setKeeperNotes] = useState(character.keeperNotes || "");
  const [lockedFields, setLockedFields] = useState<string[]>(character.lockedFields ?? []);
  const [statusDrafts, setStatusDrafts] = useState<Record<string, number | null>>(() => {
    const s: Record<string, number | null> = {};
    for (const [k, v] of Object.entries(character.status)) {
      s[k] = v as number | null;
    }
    return s;
  });
  const toggleLockedField = (field: string) => {
    setLockedFields((prev) =>
      prev.includes(field) ? prev.filter((f) => f !== field) : [...prev, field]
    );
  };

  function beginEdit() {
    setBasicDraft({
      name: character.basic.name || "",
      occupation: character.basic.occupation || "",
      age: character.basic.age || "",
      gender: character.basic.gender || ""
    });
    setAttributeDrafts(
      Object.fromEntries(character.attributes.map((attribute) => [attribute.key, String(attribute.value ?? "")]))
    );
    setKeeperNotes(character.keeperNotes || "");
    setEditing(true);
  }

  async function saveEdit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    await onUpdate(
      character.id,
      basicDraft,
      character.attributes.map((attribute) => ({
        key: attribute.key,
        value: attributeDrafts[attribute.key] ? Number(attributeDrafts[attribute.key]) : null
      })),
      keeperNotes
    );
    setEditing(false);
  }

  return (
    <article className="character-card">
      <div className="character-card__header">
        <div>
          <p className="panel__kicker">{character.ownerName}</p>
          <h2>{name}</h2>
          <p>
            {character.basic.occupation || "未读取职业"} · {character.basic.age || "年龄未知"}
          </p>
        </div>
        <span>{character.sourceFileName}</span>
      </div>

      {canEdit ? (
        <div className="character-actions">
          <button className="text-button" onClick={beginEdit} type="button">
            KP 编辑
          </button>
        </div>
      ) : null}

      {editing ? (
        <form className="character-editor" onSubmit={saveEdit}>
          <div className="character-editor__grid">
            <label>??<input value={basicDraft.name} onChange={(event) => setBasicDraft((draft) => ({ ...draft, name: event.target.value }))} /></label>
            <label>??<input value={basicDraft.occupation} onChange={(event) => setBasicDraft((draft) => ({ ...draft, occupation: event.target.value }))} /></label>
            <label>??<input value={basicDraft.age} onChange={(event) => setBasicDraft((draft) => ({ ...draft, age: event.target.value }))} /></label>
            <label>??<input value={basicDraft.gender} onChange={(event) => setBasicDraft((draft) => ({ ...draft, gender: event.target.value }))} /></label>
          </div>
          <div className="attribute-editor">
            {character.attributes.map((attribute) => (
              <label key={attribute.key}>
                {attribute.key}
                <input inputMode="numeric" value={attributeDrafts[attribute.key] ?? ""} onChange={(event) => setAttributeDrafts((draft) => ({ ...draft, [attribute.key]: event.target.value }))} />
              </label>
            ))}
          </div>
          <div className="character-editor__locked">
            <p className="character-editor__locked-title">?????????????????</p>
            <div className="character-editor__locked-grid">
              {character.attributes.map((attr) => (
                <label key={attr.key} className="locked-toggle">
                  <input type="checkbox" checked={lockedFields.includes(attr.key)} onChange={() => toggleLockedField(attr.key)} />
                  <span>{attr.key}</span>
                </label>
              ))}
            </div>
          </div>
          <label>KP ??<textarea value={keeperNotes} onChange={(event) => setKeeperNotes(event.target.value)} /></label>
          <div className="character-editor__actions">
            <button className="button button--primary" type="submit">?????</button>
            <button className="button button--ghost" onClick={() => setEditing(false)} type="button">??</button>
          </div>
        </form>
      ) : null}

      {character.warnings.length ? (
        <div className="character-warnings">
          {character.warnings.map((warning) => (
            <p key={warning}>{warning}</p>
          ))}
        </div>
      ) : null}

      <div className="attribute-grid">
        {character.attributes.map((attribute) => (
          <div key={attribute.key}>
            <span>{attribute.key}</span>
            <strong>{attribute.value ?? "?"}</strong>
            <small>
              困难 {attribute.half ?? "?"} · 极难 {attribute.fifth ?? "?"}
            </small>
            <small>
              困难 {attribute.half ?? "?"} · 极难 {attribute.fifth ?? "?"}
            </small>
            {canRoll && attribute.value ? (
              <button
                className="inline-roll"
                onClick={() => onRoll(`${name} · ${attribute.label}`, attribute.value ?? 0)}
                type="button"
              >
                投掷
              </button>
            ) : null}
          </div>
        ))}
      </div>

      {Object.keys(character.status).length > 0 && (
        <div className="status-panel">
          {Object.entries(character.status).map(([key, val]) => {
            if (val == null) return null;
            const labels: Record<string, string> = {
              hp: "HP", san: "SAN", mp: "MP", mov: "MOV",
              db: "伤害加值", build: "体格", armor: "护甲"
            };
            return (
              <div key={key} className="status-chip">
                <span className="status-chip__label">{labels[key] || key.toUpperCase()}</span>
                <span className="status-chip__value">{val}</span>
              </div>
            );
          })}
        </div>
      )}

      <div className="character-card__split">
        <div>
          <h3>技能预览</h3>
          <div className="skill-search-wrap">
            <input
              className="skill-search-input"
              placeholder="????..."
              value={skillSearch}
              onChange={(e) => setSkillSearch(e.target.value)}
            />
          </div>
          <div className="skill-list">
            {visibleSkills.map((skill) => (
              <button
                disabled={!canRoll || !skill.value}
                key={`${skill.name}-${skill.value}`}
                onClick={() => skill.value && onRoll(`${name} · ${skill.name}`, skill.value)}
                type="button"
              >
                {skill.name} {skill.value ?? "?"}
              </button>
            ))}
          </div>
          {!skillSearch && !showAllSkills && character.skills.filter((s) => s.value != null).length > 24 && (
            <button className="text-button" onClick={() => setShowAllSkills(true)} type="button">
              ??????
            </button>
          )}
        </div>
        <div>
          <h3>背景</h3>
          <div className="bg-detail">
            {Object.entries(character.background).filter(([,v]) => v).map(([k, v]) => (
              <div key={k} className="bg-item">
                <span className="bg-item__label">{
  ({"appearance":"外貌描述","beliefs":"思想与信念","significantPeople":"重要之人","significantLocations":"意义非凡之地","treasuredPossessions":"宝贵之物","traits":"特质","injuriesScars":"伤口和瘤痕","phobiasManias":"恐惧症和躁狂症","name":"姓名","player":"玩家","occupation":"职业","age":"年龄","gender":"性别","era":"时代","residence":"住地","birthplace":"故乡"} as Record<string,string>)[k] || k
}</span>
                <span className="bg-item__value">{v}</span>
              </div>
            ))}
            {Object.values(character.background).every(v => !v) && <p className="muted">暂未读取到背景文本</p>}
          </div>

          {character.weapons && character.weapons.length > 0 && (
            <><h3>武器</h3>
            <div className="weapon-list">
              {character.weapons.map((w, i) => (
                <div key={i} className="weapon-row">
                  <span className="weapon-row__name">{w.name || "武器"}</span>
                  <span className="weapon-row__dmg">{w.damage || "??"}</span>
                  {canRoll && w.skill && (
                    <button className="inline-roll" onClick={() => {
                      const sn = String(w.skill || "");
                      const sk = character.skills.find(s => s.name === sn);
                      if (sk?.value) onRoll(name + " · " + sn, sk.value);
                    }} type="button">投掷</button>
                  )}
                </div>
              ))}
            </div></>
          )}

          {character.spells && character.spells.length > 0 && (
            <><h3>法术</h3>
            <div className="bg-detail">
              {character.spells.map((s, i) => (
                <div key={i} className="bg-item">
                  <span className="bg-item__label">{s.name || "法术"}</span>
                  <span className="bg-item__value">{s.cost || ""}</span>
                </div>
              ))}
            </div></>
          )}

          {character.experiences && character.experiences.length > 0 && (
            <details className="character-history">
              <summary>调查员经历</summary>
              {character.experiences.map((exp, i) => (
                <p key={i} className="muted">{typeof exp === "string" ? exp : exp.text || JSON.stringify(exp)}</p>
              ))}
            </details>
          )}
          {character.keeperNotes ? <p className="keeper-notes">KP 备注：{character.keeperNotes}</p> : null}
        </div>
      </div>
    </article>
  );
}

function firstFilled(values: Record<string, string>) {
  return Object.values(values).find(Boolean) ?? "";
}

function formatTime(value: string) {
  return new Intl.DateTimeFormat("zh-CN", {
    hour: "2-digit",
    minute: "2-digit"
  }).format(new Date(value));
}
