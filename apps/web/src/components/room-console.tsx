"use client";

import type { FormEvent } from "react";
import { useEffect, useMemo, useRef, useState } from "react";
import type { CharacterCard, DiceRollResult, RoomDetail } from "@coc-yes/shared";
import { CharacterCardView } from "@/components/character-card-view";
import { RulesSearchPanel } from "@/components/rules-search-panel";
import { VoiceRecorder } from "@/components/voice-recorder";
import { VoiceRoom } from "@/components/voice-room";
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
const DICE_PREFS_KEY = "coc-yes.dice-prefs";

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
  const [roomPassword, setRoomPassword] = useState("");
  const [joinPassword, setJoinPassword] = useState("");
  const [joinAsSpectator, setJoinAsSpectator] = useState(false);
  const [inviteCode, setInviteCode] = useState("");
  const [playerName, setPlayerName] = useState("调查员");
  const [draft, setDraft] = useState("");
  const [rollLabel, setRollLabel] = useState("侦查");
  const [expression, setExpression] = useState("1d100");
  const [targetValue, setTargetValue] = useState(() => {
    try {
      const raw = window.localStorage.getItem(DICE_PREFS_KEY);
      if (raw) {
        const prefs = JSON.parse(raw);
        return String(prefs.targetValue ?? 60);
      }
    } catch { /* ignore */ }
    return "60";
  });
  const [bonusPenalty, setBonusPenalty] = useState("0");
  const [hiddenRoll, setHiddenRoll] = useState(false);
  const [replyTo, setReplyTo] = useState<{ id: string; senderName: string; content: string } | null>(null);
  const [sanQuickRoll, setSanQuickRoll] = useState(false);
  const [rollsFilter, setRollsFilter] = useState("");
  const [privateTarget, setPrivateTarget] = useState("");
  const [npcName, setNpcName] = useState("");
  const [whisperTarget, setWhisperTarget] = useState("");
  const [messageSearch, setMessageSearch] = useState("");
  const [characterFile, setCharacterFile] = useState<File | null>(null);
  const [notice, setNotice] = useState("创建或加入房间后，聊天会实时同步。");
  const messageEndRef = useRef<HTMLDivElement | null>(null);

  const currentMember = useMemo(
    () => room?.members.find((member) => member.id === memberId) ?? null,
    [memberId, room?.members]
  );

  // Apply room theme to document
  useEffect(() => {
    if (room?.roomTheme) {
      document.documentElement.dataset.background = room.roomTheme;
    }
  }, [room?.roomTheme]);

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
        keeperName,
        password: roomPassword || undefined
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
        displayName: playerName,
        password: joinPassword || undefined,
        role: joinAsSpectator ? "spectator" : "player"
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
    let tv: number | null = targetValue ? Number(targetValue) : null;

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

    // Save dice prefs for next time
    try {
      window.localStorage.setItem(DICE_PREFS_KEY, JSON.stringify({
        targetValue: tv ?? 60,
        expression,
        bonusPenalty: Number(bonusPenalty),
      }));
    } catch { /* ignore */ }

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

  async function createNPC(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!room || !memberId || !npcName.trim()) return;
    const name = npcName.trim();
    setNpcName("");

    const form = new FormData();
    form.append("name", name);
    form.append("keeperId", memberId);
    await fetch(apiUrl("/api/rooms/" + room.id + "/characters/npc"), {
      method: "POST",
      body: form
    });

    const detail = await apiRequest<RoomOnlyResponse>("/api/rooms/" + room.id);
    setRoom(detail.room);
    setNotice("NPC \"" + name + "\" 已创建。");
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
          <label>
            房间密码 <small>（可选，留空则无需密码）</small>
            <input value={roomPassword} onChange={(e) => setRoomPassword(e.target.value)} placeholder="留空为公开房间" />
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
          <label>
            房间密码 <small>（如房间设有密码）</small>
            <input value={joinPassword} onChange={(e) => setJoinPassword(e.target.value)} placeholder="如无密码可留空" />
          </label>
          <label className="spectator-toggle">
            <input type="checkbox" checked={joinAsSpectator} onChange={(e) => setJoinAsSpectator(e.target.checked)} />
            以旁观者身份加入（只读，不可投掷和发言）
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
              {currentMember?.role === "keeper" && (
                <div className="room-theme-picker">
                  <span className="room-theme-label">房间主题</span>
                  <select
                    className="room-theme-select"
                    value={room.roomTheme || "black"}
                    onChange={async (e) => {
                      const form = new FormData();
                      form.append("theme", e.target.value);
                      form.append("editorId", memberId || "");
                      await fetch(apiUrl("/api/rooms/" + room.id + "/theme"), { method: "POST", body: form });
                    }}
                  >
                    <option value="black">纯黑</option>
                    <option value="graphite">深灰</option>
                    <option value="green">墨绿</option>
                    <option value="blue">深蓝</option>
                    <option value="red">暗红</option>
                    <option value="sepia">羊皮纸</option>
                  </select>
                </div>
              )}
            </div>

            <div className="member-list">
              {room.members.map((member) => (
                <div className="member-item" key={member.id}>
                  <span className={member.online ? "presence presence--online" : "presence"} />
                  <div>
                    <strong>{member.displayName}</strong>
                    <small>
                      {member.role === "keeper" ? "KP" : member.role === "spectator" ? "旁观" : "玩家"}
                      {(room?.characters || []).find((c) => c.ownerId === member.id) ? " · " + ((room?.characters || []).find((c) => c.ownerId === member.id)?.basic?.name || "角色") : ""}
                    </small>
                  </div>
                </div>
              ))}
            </div>

            {currentMember?.role !== "spectator" && (
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
            {currentMember?.role === "keeper" && (
              <form className="hidden-dice-panel" onSubmit={rollDice}>
                <p className="panel__kicker">KP Only</p>
                <h3>暗骰面板</h3>
                <label>
                  标签
                  <input value={rollLabel} onChange={(e) => setRollLabel(e.target.value)} placeholder="例如: 聆听检定" />
                </label>
                <label>
                  表达式
                  <input value={expression} onChange={(e) => setExpression(e.target.value)} />
                </label>
                <label>
                  目标值
                  <input inputMode="numeric" value={targetValue} onChange={(e) => setTargetValue(e.target.value)} />
                </label>
                <label className="hidden-dice-toggle">
                  <input type="checkbox" checked={hiddenRoll} onChange={(e) => setHiddenRoll(e.target.checked)} />
                  暗骰（对玩家隐藏结果）
                </label>
                <button className="button button--ghost" type="submit">
                  暗骰投掷
                </button>
              </form>
            )}
            </form>

            )}
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

            {currentMember?.role === "keeper" && (
              <form className="npc-panel" onSubmit={createNPC}>
                <p className="panel__kicker">NPC</p>
                <h3>快速创建 NPC</h3>
                <label>
                  NPC 名称
                  <input
                    value={npcName}
                    onChange={(e) => setNpcName(e.target.value)}
                    placeholder="例如: 守夜人、图书管理员..."
                  />
                </label>
                <button className="button button--ghost" type="submit">
                  创建 NPC
                </button>
              </form>
            )}

            <button className="text-button" type="button" onClick={leaveLocalRoom}>
              仅退出本地视图
            </button>
          </aside>

          {currentMember && (
            <VoiceRoom
              roomId={room.id}
              memberId={memberId || ""}
              memberName={currentMember.displayName}
            />
          )}
          <section className="chat-panel">
            <div className="chat-search-bar">
              <input
                className="chat-search-input"
                placeholder="搜索聊天记录..."
                value={messageSearch}
                onChange={(e) => setMessageSearch(e.target.value)}
              />
              {messageSearch && (
                <button className="text-button" onClick={() => setMessageSearch("")} type="button">
                  清除
                </button>
              )}
            </div>
            <div className="chat-log">
              {room.messages
                .filter(m => {
                  if (!messageSearch) return true;
                  const q = messageSearch.toLowerCase();
                  // 搜索消息内容、发送者名、骰子标签
                  return (
                    m.content.toLowerCase().includes(q) ||
                    m.senderName.toLowerCase().includes(q) ||
                    (m.roll?.label && m.roll.label.toLowerCase().includes(q))
                  );
                })
                .map((message) => (
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
              {messageSearch && room.messages.filter(m => {
                const q = messageSearch.toLowerCase();
                return m.content.toLowerCase().includes(q) || m.senderName.toLowerCase().includes(q) || (m.roll?.label && m.roll.label.toLowerCase().includes(q));
              }).length === 0 && (
                <p className="chat-search-empty">没有找到匹配的消息</p>
              )}
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
          {room.characters.map((character) => {
            const isNPC = character.basic.occupation === "NPC" || character.sourceFileName === "npc";
            const isOwner = character.ownerId === memberId;
            const ownerChars = room.characters?.filter(c => c.ownerId === character.ownerId) || [];
            const hasMulti = ownerChars.length > 1;
            const isActive = character.active !== false;
            return (
              <div key={character.id} className={(isNPC ? "character-card--npc-wrapper" : "") + (hasMulti && !isActive ? " character-card--inactive" : "")}>
                {isNPC && (
                  <div className="npc-card-header">
                    <span className="npc-badge">NPC</span>
                    <span className="npc-name">{character.basic.name || "NPC"}</span>
                  </div>
                )}
                {hasMulti && !isNPC && isOwner && (
                  <div className={"multi-char-bar" + (isActive ? " multi-char-bar--active" : "")}>
                    <span className="multi-char-indicator">{isActive ? "当前角色" : "备用角色"}</span>
                    <span className="multi-char-count">{ownerChars.findIndex(c => c.id === character.id) + 1}/{ownerChars.length}</span>
                  </div>
                )}
                <CharacterCardView
                  canEdit={currentMember?.role === "keeper"}
                  canRoll={Boolean(currentMember) && isActive}
                  character={character}
                  onRoll={rollCharacterCheck}
                  onUpdate={updateCharacter}
                />
              </div>
            );
          })}
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

function firstFilled(values: Record<string, string>) {
  return Object.values(values).find(Boolean) ?? "";
}

function formatTime(value: string) {
  return new Intl.DateTimeFormat("zh-CN", {
    hour: "2-digit",
    minute: "2-digit"
  }).format(new Date(value));
}
