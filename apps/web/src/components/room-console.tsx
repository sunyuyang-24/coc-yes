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
import { SettingsPanel, loadSettings } from "@/components/settings-panel";
import { SanCheckPanel } from "@/components/san-check-panel";
import { CombatPanel } from "@/components/combat-panel";
import { ChasePanel } from "@/components/chase-panel";
import { apiRequest, apiUrl, wsUrl } from "@/lib/api";

type RoomResponse = { room: RoomDetail; currentMemberId: string };
type RoomOnlyResponse = { room: RoomDetail };
type SocketEvent = { type: "room_state" | "room_update"; room: RoomDetail };
const STORAGE_KEY = "coc-yes.current-session";
const DICE_PREFS_KEY = "coc-yes.dice-prefs";

let _audioCtx: AudioContext | null = null;
function _getAudioCtx(): AudioContext | null {
  if (_audioCtx) return _audioCtx;
  try { _audioCtx = new AudioContext(); } catch { /* init */ }
  return _audioCtx;
}
function playDiceSound() {
  const ctx = _getAudioCtx(); if (!ctx) return;
  try { ctx.resume().then(() => { const now = ctx.currentTime;
    for (let i = 0; i < 3; i++) { const osc = ctx.createOscillator(); const gain = ctx.createGain();
      osc.type = "triangle"; osc.frequency.setValueAtTime(800 + Math.random() * 400, now + i * 0.06);
      osc.frequency.exponentialRampToValueAtTime(200, now + i * 0.06 + 0.08);
      gain.gain.setValueAtTime(0.15, now + i * 0.06); gain.gain.exponentialRampToValueAtTime(0.001, now + i * 0.06 + 0.1);
      osc.connect(gain); gain.connect(ctx.destination); osc.start(now + i * 0.06); osc.stop(now + i * 0.06 + 0.1); } }); } catch { /* ignore */ }
}
function isNpcChar(c: CharacterCard): boolean {
  return !!(c.isNpc) || (c.sourceFileName || "").startsWith("npc");
}
function findMemberChar(memberId: string, chars: CharacterCard[] | undefined): CharacterCard | undefined {
  return chars?.find((c) => c.ownerId === memberId && c.active !== false && !isNpcChar(c));
}

export function RoomConsole() {
  const [room, setRoom] = useState<RoomDetail | null>(null);
  const [memberId, setMemberId] = useState<string | null>(null);
  const [roomName, setRoomName] = useState(""); const [keeperName, setKeeperName] = useState("KP");
  const [roomPassword, setRoomPassword] = useState(""); const [joinPassword, setJoinPassword] = useState("");
  const [joinAsSpectator, setJoinAsSpectator] = useState(false);
  const [inviteCode, setInviteCode] = useState(""); const [playerName, setPlayerName] = useState("");
  const [draft, setDraft] = useState(""); const [rollLabel, setRollLabel] = useState("");
  const [expression, setExpression] = useState("1d100");
  const [targetValue, setTargetValue] = useState(() => { try { const raw = window.localStorage.getItem(DICE_PREFS_KEY);
    if (raw) { const prefs = JSON.parse(raw); return String(prefs.targetValue ?? 60); } } catch { /* ignore */ } return "60"; });
  const [bonusPenalty, setBonusPenalty] = useState("0"); const [hiddenRoll, setHiddenRoll] = useState(false);
  const [replyTo, setReplyTo] = useState<{ id: string; senderName: string; content: string } | null>(null);
  const [privateTarget, setPrivateTarget] = useState(""); const [npcName, setNpcName] = useState("");
  const [npcText, setNpcText] = useState(""); const [npcCreating, setNpcCreating] = useState(false);
  const [messageSearch, setMessageSearch] = useState("");
  const [characterFile, setCharacterFile] = useState<File | null>(null); const [notice, setNotice] = useState("");
  useEffect(() => { if (!notice) return; const id = setTimeout(() => setNotice(""), 5000); return () => clearTimeout(id); }, [notice]);
  const [wsStatus, setWsStatus] = useState<"connecting" | "connected" | "disconnected">("disconnected");
  const [showRulesPanel, setShowRulesPanel] = useState(false);
  const [showSummaryPanel, setShowSummaryPanel] = useState(false);
  const [showSettingsPanel, setShowSettingsPanel] = useState(false);
  const [selectedCharId, setSelectedCharId] = useState<string | null>(null);
  const [showSkillDropdown, setShowSkillDropdown] = useState(false);
  const [showAttrDropdown, setShowAttrDropdown] = useState(false);
  const [showDicePanel, setShowDicePanel] = useState(false);
  const [showIntroEditor, setShowIntroEditor] = useState(false);
  const [introDraft, setIntroDraft] = useState("");
  const [voiceMode, setVoiceMode] = useState<"off" | "push" | "voice">("off");
  const [checkDifficulty, setCheckDifficulty] = useState<"regular" | "hard" | "extreme">("regular");
  const [showSanCheckPanel, setShowSanCheckPanel] = useState(false);
  const [showCombatPanel, setShowCombatPanel] = useState(false);
  const [showChasePanel, setShowChasePanel] = useState(false);
  const [showNpcPanel, setShowNpcPanel] = useState(false);
  const [showNpcList, setShowNpcList] = useState(false);
  const [kpCheckCharId, setKpCheckCharId] = useState("");
  const [attachment, setAttachment] = useState<{ url: string; filename: string; size: number; contentType: string } | null>(null);
  const [uploading, setUploading] = useState(false);
  const [dragOver, setDragOver] = useState(false);
  const [viewingFile, setViewingFile] = useState<{ url: string; filename: string; contentType: string } | null>(null);
  const messageEndRef = useRef<HTMLDivElement | null>(null);
  const currentMember = useMemo(() => room?.members.find((m) => m.id === memberId) ?? null, [memberId, room?.members]);
  useEffect(() => { if (room?.roomTheme) document.documentElement.dataset.background = room.roomTheme; }, [room?.roomTheme]);
  useEffect(() => { const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return; try { const session = JSON.parse(raw) as { roomId: string; memberId: string };
    apiRequest<RoomOnlyResponse>(`/api/rooms/${session.roomId}`).then(({ room: restoredRoom }) => {
      if (restoredRoom.status === "ended") { window.localStorage.removeItem(STORAGE_KEY); return; }
      setRoom(restoredRoom); setMemberId(session.memberId); setNotice(""); }).catch((err) => {
        if (err && typeof err === 'object' && 'status' in err && (err as any).status === 404) {
          window.localStorage.removeItem(STORAGE_KEY);
        }
      }); } catch { /* ignore */ } }, []);
  useEffect(() => { if (!room || !memberId) return; let socket: WebSocket;
    let reconnectTimer: ReturnType<typeof setTimeout> | null = null; let mounted = true;
    function connect() { if (!mounted || !room) return; setWsStatus("connecting");
      const url = `${wsUrl(`/api/rooms/${room.id}/ws`)}?member_id=${encodeURIComponent(memberId!)}`;
      socket = new WebSocket(url);
      socket.onmessage = (event) => {
        try {
          const payload = JSON.parse(event.data) as SocketEvent;
          if (payload.type === "room_state" || payload.type === "room_update") setRoom(payload.room);
        } catch (err) {
          console.error("Invalid WebSocket message:", err);
        }
      };
      socket.onopen = () => { setWsStatus("connected"); if (reconnectTimer) { clearTimeout(reconnectTimer); reconnectTimer = null; } };
      socket.onerror = (err) => console.error("WebSocket error:", err);
      socket.onclose = () => { if (!mounted) return; setWsStatus("disconnected"); let delay = 3000;
        const attempt = () => { if (!mounted) return; reconnectTimer = setTimeout(() => { connect(); }, delay);
          delay = Math.min(delay * 2, 30000); }; attempt(); }; }
    connect(); return () => { mounted = false; if (reconnectTimer) clearTimeout(reconnectTimer); socket.close(); }; }, [memberId, room?.id]);
  useEffect(() => { if (loadSettings().autoScrollChat !== false) { messageEndRef.current?.scrollIntoView({ behavior: "smooth", block: "end" }); } }, [room?.messages.length]);


  const filteredMessages = useMemo(() => {
    if (!room) return [];
    if (!messageSearch) return room.messages;
    const q = messageSearch.toLowerCase();
    return room.messages.filter((m) =>
      m.content.toLowerCase().includes(q) || m.senderName.toLowerCase().includes(q) ||
      (m.roll?.label && m.roll.label.toLowerCase().includes(q))
    );
  }, [room?.messages, messageSearch]);

  async function createRoom(event: FormEvent<HTMLFormElement>) { event.preventDefault();
    try {
      const response = await apiRequest<RoomResponse>("/api/rooms", { method: "POST",
        body: JSON.stringify({ name: roomName, keeper_name: keeperName, password: roomPassword || undefined }) });
      enterRoom(response.room, response.currentMemberId);
    } catch (err) { setNotice("创建房间失败，请检查网络连接"); } }
  async function joinRoom(event: FormEvent<HTMLFormElement>) { event.preventDefault();
    try {
      const response = await apiRequest<RoomResponse>("/api/rooms/join", { method: "POST",
        body: JSON.stringify({ inviteCode, displayName: playerName, password: joinPassword || undefined,
          role: joinAsSpectator ? "spectator" : "player" }) });
      enterRoom(response.room, response.currentMemberId);
    } catch (err) { setNotice("加入房间失败，请检查网络连接"); } }
  async function uploadFile(file: File) {
    if (!room || !memberId) return;
    setUploading(true);
    try {
      const form = new FormData();
      form.append("senderId", memberId);
      form.append("file", file);
      const res = await fetch(apiUrl(`/api/rooms/${room.id}/files`), { method: "POST", body: form });
      if (!res.ok) { const err = await res.text(); alert(`上传失败: ${err}`); return null; }
      return await res.json() as { url: string; filename: string; size: number; contentType: string };
    } catch (err) { alert(`上传出错: ${err instanceof Error ? err.message : "网络错误"}`); return null; }
    finally { setUploading(false); }
  }
  async function sendMessage(event: FormEvent<HTMLFormElement>) { event.preventDefault();
    if (!room || !memberId) return;
    if (!draft.trim() && !attachment) return;
    const content = draft.trim(); setDraft("");
    try { await apiRequest(`/api/rooms/${room.id}/messages`, { method: "POST",
      body: JSON.stringify({ senderId: memberId, content, replyTo,
        privateTo: privateTarget || undefined, attachment: attachment || undefined }) });
      setReplyTo(null); setAttachment(null); }
    catch { setNotice("发送失败，请检查网络连接"); } }
  async function rollDice(event?: FormEvent<HTMLFormElement>) { if (event) event.preventDefault();
    if (!room || !memberId) return; const parsed = Number(targetValue);
    const tv: number | null = Number.isFinite(parsed) ? parsed : null;
    try { await apiRequest(`/api/rooms/${room.id}/rolls`, { method: "POST",
      body: JSON.stringify({ rollerId: memberId, expression, label: rollLabel || null, targetValue: tv,
        bonusPenalty: Number(bonusPenalty), hidden: hiddenRoll && currentMember?.role === "keeper" }) });
    try { window.localStorage.setItem(DICE_PREFS_KEY, JSON.stringify({ targetValue: tv ?? 60, expression,
      bonusPenalty: Number(bonusPenalty) })); } catch { /* ignore */ } if (loadSettings().diceSound !== false) playDiceSound(); }
    catch { setNotice("投骰失败，请检查网络连接"); } }
  async function rollCharacterCheck(label: string, targetValue: number, bonusPenalty?: number) {
    if (!room || !memberId) return;
    try { await apiRequest(`/api/rooms/${room.id}/rolls`, { method: "POST",
      body: JSON.stringify({ rollerId: memberId, expression: "1d100", label, targetValue,
        bonusPenalty: bonusPenalty ?? 0 }) }); if (loadSettings().diceSound !== false) playDiceSound(); }
    catch { setNotice("投骰失败，请检查网络连接"); } }
  async function updateCharacter(characterId: string, basic: Record<string, string>,
    attributes: Array<{ key: string; value: number | null }>, keeperNotes: string,
    lockedFields: string[], status: Record<string, number | null>) {
    if (!room || !memberId) return; await apiRequest(`/api/rooms/${room.id}/characters/${characterId}`,
      { method: "PATCH", body: JSON.stringify({ editorId: memberId, basic, attributes, keeperNotes,
        locked_fields: lockedFields, status }) });
    const detail = await apiRequest<RoomOnlyResponse>(`/api/rooms/${room.id}`); setRoom(detail.room); }
  async function uploadCharacter(event: FormEvent<HTMLFormElement>) { event.preventDefault();
    if (!room || !memberId || !characterFile) return; const body = new FormData();
    body.append("ownerId", memberId); body.append("file", characterFile);
    try {
      const response = await fetch(apiUrl(`/api/rooms/${room.id}/characters/upload`), { method: "POST", body });
      if (!response.ok) { const errText = await response.text(); alert(`上传失败: ${errText}`); return; }
      const detail = await apiRequest<RoomOnlyResponse>(`/api/rooms/${room.id}`); setRoom(detail.room);
      setCharacterFile(null);
    } catch (err) { alert(`上传角色卡出错: ${err instanceof Error ? err.message : "网络错误"}`); } }
  const [showKpLeaveConfirm, setShowKpLeaveConfirm] = useState(false);
  const [leaving, setLeaving] = useState(false);
  const [deleteMsgId, setDeleteMsgId] = useState<string | null>(null);
  const [deleting, setDeleting] = useState(false);
  const [deleteNpcId, setDeleteNpcId] = useState<string | null>(null);
  const [deletingNpc, setDeletingNpc] = useState(false);
  async function leaveLocalRoom() {
    if (!room || !memberId) return;
    setLeaving(true);
    try {
      if (isKeeper) {
        const form = new FormData(); form.append("editorId", memberId);
        await fetch(apiUrl(`/api/rooms/${room.id}/delete`), { method: "POST", body: form });
      } else {
        const form = new FormData(); form.append("memberId", memberId);
        await fetch(apiUrl(`/api/rooms/${room.id}/characters/remove`), { method: "POST", body: form });
      }
    } catch { /* ignore errors during cleanup */ }
    finally {
      setRoom(null); setMemberId(null); window.localStorage.removeItem(STORAGE_KEY);
      document.documentElement.dataset.background = "black";
      setLeaving(false); setShowKpLeaveConfirm(false);
    }
  }
  async function deleteMessage() {
    if (!room || !memberId || !deleteMsgId) return;
    setDeleting(true);
    try {
      const form = new FormData(); form.append("editorId", memberId);
      await fetch(apiUrl(`/api/rooms/${room.id}/messages/${deleteMsgId}/delete`), { method: "POST", body: form });
      const detail = await apiRequest<RoomOnlyResponse>(`/api/rooms/${room.id}`); setRoom(detail.room);
    } catch { /* WebSocket room_update will refresh */ }
    finally { setDeleting(false); setDeleteMsgId(null); }
  }
  async function deleteNpc() {
    if (!room || !memberId || !deleteNpcId) return;
    setDeletingNpc(true);
    try {
      const form = new FormData(); form.append("editorId", memberId);
      await fetch(apiUrl(`/api/rooms/${room.id}/characters/${deleteNpcId}/delete`), { method: "POST", body: form });
      const detail = await apiRequest<RoomOnlyResponse>(`/api/rooms/${room.id}`); setRoom(detail.room);
      setSelectedCharId(null);
    } catch { /* WebSocket room_update will refresh */ }
    finally { setDeletingNpc(false); setDeleteNpcId(null); }
  }
  async function createNPC(event: FormEvent<HTMLFormElement>) { event.preventDefault();
    if (!room || !memberId || !npcName.trim()) return; const name = npcName.trim(); setNpcName("");
    const form = new FormData(); form.append("name", name); form.append("keeperId", memberId);
    try {
      await fetch(apiUrl("/api/rooms/" + room.id + "/characters/npc"), { method: "POST", body: form });
      const detail = await apiRequest<RoomOnlyResponse>("/api/rooms/" + room.id); setRoom(detail.room);
    } catch { /* WebSocket room_update will refresh state */ } }
  async function createNPCFromText() {
    if (!room || !memberId || !npcText.trim()) return;
    setNpcCreating(true);
    try {
      const form = new FormData(); form.append("keeperId", memberId); form.append("npcText", npcText.trim());
      const res = await fetch(apiUrl(`/api/rooms/${room.id}/characters/npc/text`), { method: "POST", body: form });
      if (!res.ok) { const err = await res.json(); setNotice(`NPC 创建失败: ${err.detail || res.statusText}`); return; }
      setNpcText(""); setShowNpcPanel(false);
      const detail = await apiRequest<RoomOnlyResponse>(`/api/rooms/${room.id}`); setRoom(detail.room);
    } catch { /* WebSocket room_update will refresh */ }
    finally { setNpcCreating(false); }
  }
  function enterRoom(nextRoom: RoomDetail, nextMemberId: string) { setRoom(nextRoom); setMemberId(nextMemberId);
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify({ roomId: nextRoom.id, memberId: nextMemberId })); }
  async function saveModuleIntro() {
    if (!room || !memberId) return;
    await apiRequest(`/api/rooms/${room.id}/intro`, { method: "PATCH",
      body: JSON.stringify({ editorId: memberId, intro: introDraft }) });
    setShowIntroEditor(false); }
  async function structuredCheck(type: "skill" | "attr", name: string, value: number, difficulty: "regular" | "hard" | "extreme", hidden: boolean) {
    if (!room || !memberId) return;
    const charId = isKeeper ? kpCheckCharId : myChar?.id;
    if (!charId) return;
    await apiRequest(`/api/rooms/${room.id}/rolls/check`, { method: "POST",
      body: JSON.stringify({ characterId: charId, [type === "skill" ? "skillName" : "attributeKey"]: name, difficulty, hidden }) });
    if (loadSettings().diceSound !== false) playDiceSound(); }
  async function startCombat() { if (!room || !memberId) return;
    const form = new FormData(); form.append("editorId", memberId);
    try { await fetch(apiUrl(`/api/rooms/${room.id}/combat/start`), { method: "POST", body: form }); }
    catch { /* ignore */ } }
  async function endCombat() { if (!room || !memberId) return;
    const form = new FormData(); form.append("editorId", memberId);
    try { await fetch(apiUrl(`/api/rooms/${room.id}/combat/end`), { method: "POST", body: form }); }
    catch { /* ignore */ } }
  async function startChase() { if (!room || !memberId) return;
    const form = new FormData(); form.append("editorId", memberId);
    try { await fetch(apiUrl(`/api/rooms/${room.id}/chase/start`), { method: "POST", body: form }); }
    catch { /* ignore */ } }
  async function endChase() { if (!room || !memberId) return;
    const form = new FormData(); form.append("editorId", memberId);
    try { await fetch(apiUrl(`/api/rooms/${room.id}/chase/end`), { method: "POST", body: form }); }
    catch { /* ignore */ } }
  const isKeeper = currentMember?.role === "keeper";


  // ---- RENDER: Setup screens (no room active) ----
  if (!room) {
    return (
      <section className="setup-screens">
        <form className="setup-card" onSubmit={createRoom}>
          <p className="panel__kicker">✦ Keeper</p>
          <h2>创建房间</h2>
          <p className="setup-card__desc">作为守秘人主持一场克苏鲁的呼唤游戏</p>
          <div className="setup-card__fields">
            <label>房间名
              <input type="text" value={roomName} onChange={(e) => setRoomName(e.target.value)}
                placeholder="例如：暗黑边缘" autoFocus />
            </label>
            <label>KP 名称
              <input type="text" value={keeperName} onChange={(e) => setKeeperName(e.target.value)} />
            </label>
            <label>密码 <small>（选填）</small>
              <input type="password" value={roomPassword} onChange={(e) => setRoomPassword(e.target.value)} placeholder="不设密码" />
            </label>
          </div>
          <div className="setup-card__actions">
            <button className="button button--primary" type="submit">创建游戏房间</button>
          </div>
        </form>
        <form className="setup-card" onSubmit={joinRoom}>
          <p className="panel__kicker">◈ Investigator</p>
          <h2>加入房间</h2>
          <p className="setup-card__desc">使用邀请码加入已存在的游戏房间</p>
          <div className="setup-card__fields">
            <label>邀请码
              <input type="text" value={inviteCode} onChange={(e) => setInviteCode(e.target.value.toUpperCase())}
                placeholder="例如 A1B2C3" />
            </label>
            <label>显示名
              <input type="text" value={playerName} onChange={(e) => setPlayerName(e.target.value)} />
            </label>
            <label>密码 <small>（选填）</small>
              <input type="password" value={joinPassword} onChange={(e) => setJoinPassword(e.target.value)} placeholder="不设密码" />
            </label>
            <label className="spectator-toggle">
              <input type="checkbox" checked={joinAsSpectator} onChange={(e) => setJoinAsSpectator(e.target.checked)} />
              以观察者身份加入（只看不说）
            </label>
          </div>
          <div className="setup-card__actions">
            <button className="button button--ghost" type="submit">加入游戏房间</button>
          </div>
        </form>
      </section>
    );
  }

  // ---- RENDER: Room (redesigned layout) ----
  const selectedChar = selectedCharId ? room.characters?.find((c) => c.id === selectedCharId) : null;
  const myChar = memberId ? findMemberChar(memberId, room.characters) : null;

  return (
    <div className="room-layout">
      {/* Notice Banner */}
      {notice && (
        <div className="notice-banner" role="alert">
          <span>{notice}</span>
          <button onClick={() => setNotice("")} type="button" aria-label="关闭">&times;</button>
        </div>
      )}

      {/* Room Header */}
      <header className="room-header">
        <div className="room-header__info">
          <div style={{ display: "flex", alignItems: "baseline", gap: "8px" }}>
            <span className="room-header__title">{room.name}</span>
            <span className="room-header__scenario">
              {room.status === "preparing" ? "准备中" : room.status === "active" ? "进行中" : "已结束"}
            </span>
            {room.moduleIntro && (
              <button className="button button--ghost button--sm" onClick={() => setShowIntroEditor(true)} type="button">
                {isKeeper ? "编辑简介" : "查看简介"}
              </button>
            )}
            {isKeeper && !room.moduleIntro && (
              <button className="button button--ghost button--sm" onClick={() => { setIntroDraft(""); setShowIntroEditor(true); }} type="button">
                + 添加模组简介
              </button>
            )}
          </div>
          <div className="room-header__desc">
            {isKeeper ? "KP | " : ""}{currentMember?.displayName} | 邀请码: {room.inviteCode}
          </div>
        </div>
        <div className="room-header__actions">
          <div className="room-header__invite">
            <span>邀请码</span>
            <code>{room.inviteCode}</code>
          </div>
          <span style={{ fontSize: "11px", color: "var(--text-muted)" }}>
            {wsStatus === "connected" ? "已连接" : wsStatus === "connecting" ? "连接中" : "已断开"}
          </span>
          {isKeeper && (
            <select style={{ height: "30px", padding: "0 8px", fontSize: "12px" }}
              value={room.roomTheme || "black"}
              onChange={async (e) => {
                const form = new FormData(); form.append("theme", e.target.value);
                form.append("editorId", memberId || "");
                try { await fetch(apiUrl("/api/rooms/" + room.id + "/theme"), { method: "POST", body: form }); }
                catch { /* ignore */ }
              }}>
              <option value="black">纯黑</option>
              <option value="graphite">深灰</option>
              <option value="green">墨绿</option>
              <option value="blue">深蓝</option>
              <option value="red">暗红</option>
              <option value="sepia">羊皮纸</option>
            </select>
          )}
          <button className="button button--ghost button--sm"
            onClick={() => isKeeper ? setShowKpLeaveConfirm(true) : leaveLocalRoom()}
            disabled={leaving} type="button">
            {leaving ? "退出中..." : "离开房间"}
          </button>
        </div>
      </header>

      {/* Module Intro Editor Modal */}
      {showIntroEditor && (
        <div className="modal-overlay" onClick={() => setShowIntroEditor(false)}>
          <div className="modal-panel" onClick={(e) => e.stopPropagation()} style={{ maxWidth: "500px" }}>
            <div className="drawer__header">
              <span className="drawer__title">模组简介</span>
              <button className="button button--ghost button--sm" onClick={() => setShowIntroEditor(false)} type="button">✕</button>
            </div>
            {isKeeper ? (
              <div style={{ padding: "16px", display: "flex", flexDirection: "column", gap: "12px" }}>
                <textarea value={introDraft || room.moduleIntro || ""} onChange={(e) => setIntroDraft(e.target.value)}
                  placeholder="写入模组简介，支持 Markdown..." rows={8}
                  style={{ width: "100%", background: "var(--bg)", color: "var(--text)", border: "1px solid var(--border)",
                    borderRadius: "var(--radius)", padding: "10px", fontSize: "13px", fontFamily: "var(--font)", resize: "vertical" }} />
                <div style={{ display: "flex", gap: "8px", justifyContent: "flex-end" }}>
                  <button className="button button--ghost button--sm" onClick={() => setShowIntroEditor(false)} type="button">取消</button>
                  <button className="button button--primary button--sm" onClick={saveModuleIntro} type="button">保存</button>
                </div>
              </div>
            ) : (
              <div style={{ padding: "16px", maxHeight: "400px", overflowY: "auto", fontSize: "14px", lineHeight: 1.7, color: "var(--text-secondary)" }}>
                {(room.moduleIntro || "").split("\n").map((line, i) => <p key={i} style={{ margin: "4px 0" }}>{line || " "}</p>)}
              </div>
            )}
          </div>
        </div>
      )}

      <div className="room-body">
        {/* Left Toolbar */}
        <aside className="left-toolbar">
          <div className="left-toolbar__section">
            <button className={`left-toolbar__btn ${showSettingsPanel ? "left-toolbar__btn--active" : ""}`}
              onClick={() => setShowSettingsPanel(!showSettingsPanel)} type="button">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="3"/><path d="M12 1v2M12 21v2M4.22 4.22l1.42 1.42M18.36 18.36l1.42 1.42M1 12h2M21 12h2M4.22 19.78l1.42-1.42M18.36 5.64l1.42-1.42"/></svg>
              设置
            </button>
            {showSettingsPanel && (
              <div className="left-toolbar__panel">
                <SettingsPanel />
              </div>
            )}
          </div>

          {isKeeper && (
            <div className="left-toolbar__section">
              <p className="left-toolbar__label">KP 工具</p>
              <button className={`left-toolbar__btn ${showRulesPanel ? "left-toolbar__btn--active" : ""}`}
                onClick={() => setShowRulesPanel(!showRulesPanel)} type="button">📖 规则书检索</button>
              {showRulesPanel && (
                <div className="left-toolbar__panel">
                  <RulesSearchPanel showSendToChat onSendToChat={(text) => { setDraft(text); }} />
                </div>
              )}
              <button className={`left-toolbar__btn ${showSummaryPanel ? "left-toolbar__btn--active" : ""}`}
                onClick={() => setShowSummaryPanel(!showSummaryPanel)} type="button">📋 游戏摘要</button>
              {showSummaryPanel && (
                <div className="left-toolbar__panel">
                  <SummaryPanel room={room} memberId={memberId!} isKeeper={isKeeper} />
                </div>
              )}
              <button className={`left-toolbar__btn ${showNpcPanel ? "left-toolbar__btn--active" : ""}`}
                onClick={() => { setShowNpcPanel(!showNpcPanel); setShowNpcList(false); }} type="button">🧟 新建 NPC</button>
              {showNpcPanel && (
                <div className="left-toolbar__panel">
                  <p style={{ fontSize: "11px", color: "var(--text-muted)", margin: "0 0 8px" }}>
                    输入属性文本，自动解析创建 NPC 角色卡。支持中英文属性名
                  </p>
                  <textarea
                    value={npcText}
                    onChange={(e) => setNpcText(e.target.value)}
                    placeholder={"例如：\n梅洛迪亚斯·杰弗逊 58岁，守墓人\n力量 45 体质 65 体型 60 敏捷 50\n智力 70 外貌 55 意志 60 教育 65\n理智值 60 HP 12\n技能: 侦查 55, 潜行 40\n武器: 铁锹 1d6\n背景: 一个老守墓人"}
                    rows={10}
                    style={{
                      width: "100%", padding: "8px 10px", background: "var(--bg)",
                      border: "1px solid var(--border)", borderRadius: "var(--radius-sm)",
                      color: "var(--text)", fontFamily: "var(--font)", fontSize: "12px",
                      outline: "none", resize: "vertical", lineHeight: "1.5",
                    }}
                  />
                  <button className="button button--primary button--sm"
                    onClick={createNPCFromText} type="button" disabled={npcCreating || !npcText.trim()}
                    style={{ marginTop: "8px", width: "100%" }}>
                    {npcCreating ? "创建中..." : "创建 NPC"}
                  </button>
                </div>
              )}
              {/* Existing NPC list */}
              {room.characters?.filter((c) => isNpcChar(c)).length ? (
                <>
                  <button className={`left-toolbar__btn ${showNpcList ? "left-toolbar__btn--active" : ""}`}
                    onClick={() => { setShowNpcList(!showNpcList); setShowNpcPanel(false); }} type="button">
                    📋 NPC 列表 ({room.characters.filter((c) => isNpcChar(c)).length})
                  </button>
                  {showNpcList && (
                    <div className="left-toolbar__panel">
                      {room.characters.filter((c) => isNpcChar(c)).map((npc) => (
                        <div key={npc.id} style={{
                          display: "flex", alignItems: "center", gap: "8px",
                          padding: "6px 8px", borderRadius: "var(--radius-sm)",
                          cursor: "pointer", fontSize: "13px",
                          background: selectedCharId === npc.id ? "var(--bg-active)" : "transparent",
                        }}>
                          <span style={{ flex: 1, color: selectedCharId === npc.id ? "var(--brand)" : "var(--text-secondary)" }}
                            onClick={() => setSelectedCharId(selectedCharId === npc.id ? null : npc.id)}>
                            {npc.basic?.name || "未命名"}
                          </span>
                          <span style={{ fontSize: "10px", color: "var(--text-muted)" }}>
                            HP {npc.status?.hp ?? "?"}
                          </span>
                          <button type="button"
                            onClick={(e) => { e.stopPropagation(); setDeleteNpcId(npc.id); }}
                            title="删除 NPC"
                            style={{ background: "none", border: "none", color: "var(--text-muted)", cursor: "pointer", fontSize: "12px", padding: "1px 4px", borderRadius: "3px" }}
                            onMouseOver={(e) => (e.currentTarget.style.color = "var(--error)")}
                            onMouseOut={(e) => (e.currentTarget.style.color = "var(--text-muted)")}>
                            ✕
                          </button>
                        </div>
                      ))}
                    </div>
                  )}
                </>
              ) : null}
            </div>
          )}

          <div className="left-toolbar__section">
            <p className="left-toolbar__label">骰子记录</p>
            <div style={{ fontSize: "11px", color: "var(--text-muted)", padding: "4px 8px" }}>
              {room.rolls?.length ? `${room.rolls.length} 次投掷` : "暂无记录"}
            </div>
            <div style={{ maxHeight: "160px", overflowY: "auto" }}>
              {[...(room.rolls ?? [])].reverse().slice(0, 30).map((roll) => (
                <div key={roll.id} style={{ fontSize: "11px", padding: "2px 8px", color: roll.hidden ? "var(--error)" : "var(--text-secondary)" }}>
                  {formatTime(roll.createdAt)} {roll.rollerName} - {roll.expression} - {roll.hidden ? "暗投" : `${roll.total}${roll.successLabel ? ` (${roll.successLabel})` : ""}`}
                </div>
              ))}
            </div>
          </div>

          {/* Character card upload — only for players */}
          {!isKeeper && (
            <div className="left-toolbar__section">
              <p className="left-toolbar__label">角色卡</p>
              <form onSubmit={uploadCharacter} style={{ display: "flex", flexDirection: "column", gap: "6px", padding: "4px 8px" }}>
                <label style={{ fontSize: "11px", color: "var(--text-secondary)", cursor: "pointer" }}>
                  <input type="file" accept=".xlsx,.xls,.json,.txt"
                    onChange={(e) => { const file = e.target.files?.[0]; if (file) setCharacterFile(file); }}
                    style={{ display: "none" }}
                    id="character-file-input" />
                  <span className={`left-toolbar__file-chip${characterFile || myChar ? " left-toolbar__file-chip--active" : ""}`}
                    onClick={() => document.getElementById("character-file-input")?.click()}>
                    {characterFile ? characterFile.name : myChar ? "更换角色卡文件" : "选择角色卡文件"}
                  </span>
                </label>
                {characterFile && (
                  <button className="button button--primary button--sm" type="submit">
                    {myChar ? "更新角色卡" : "上传角色卡"}
                  </button>
                )}
                {myChar && !characterFile && (
                  <span style={{ fontSize: "11px", color: "var(--success)", padding: "0 4px" }}>
                    已绑定: {myChar.basic?.name || "未命名"}
                  </span>
                )}
              </form>
            </div>
          )}
        </aside>


        {/* Center Chat Column */}
        <div className="chat-column">
          <div className="chat-column__search">
            <input placeholder="搜索消息..." value={messageSearch} onChange={(e) => setMessageSearch(e.target.value)} />
            {messageSearch && <button className="button button--ghost button--sm" onClick={() => setMessageSearch("")} type="button">清除</button>}
          </div>
          <div className="chat-column__messages">
            {filteredMessages.length === 0 ? (
              <p style={{ textAlign: "center", color: "var(--text-muted)", padding: "32px 16px", fontSize: "14px" }}>
                {messageSearch ? "无匹配消息" : "暂无消息，开始聊天吧"}
              </p>
            ) : (
              filteredMessages.map((message) => {
                const isSystem = message.type === "system"; const isDice = message.type === "dice_roll";
                const isHidden = message.roll?.hidden; const isPrivate = message.type === "private";
                const isVoice = message.type === "voice"; const isKeeperMsg = message.senderRole === "keeper";
                const bubbleClass = isSystem ? "chat-bubble--system" : isHidden ? "chat-bubble--hidden" :
                  isDice ? "chat-bubble--dice" : isPrivate ? "chat-bubble--private" :
                  isVoice ? "chat-bubble--voice" : "chat-bubble--text";
                return (
                  <article className={`chat-bubble ${bubbleClass}`} key={message.id}>
                    {!isSystem && (
                      <div className="chat-bubble__header">
                        <span className={`chat-bubble__sender ${isKeeperMsg ? "chat-bubble__sender--kp" : "chat-bubble__sender--player"}`}>
                          {message.senderName}
                        </span>
                        {isHidden && <span style={{ fontSize: "10px", color: "var(--error)" }}>暗投</span>}
                        {isPrivate && <span style={{ fontSize: "10px", color: "#7C6FF7" }}>私密</span>}
                        <span className="chat-bubble__time">{formatTime(message.createdAt)}</span>
                        {(isKeeper || message.senderId === memberId) && (
                          <button type="button" className="chat-bubble__delete"
                            onClick={() => setDeleteMsgId(message.id)}
                            title="删除消息">✕</button>
                        )}
                      </div>
                    )}
                    {message.replyTo && (
                      <div className="chat-bubble__reply">
                        {message.replyTo.senderName}: {message.replyTo.content.slice(0, 60)}
                      </div>
                    )}
                    {isDice && message.roll ? (
                      <DiceRollView roll={message.roll} />
                    ) : isVoice ? (
                      <VoiceMessage roomId={room.id} url={message.content} duration={0} />
                    ) : (
                      <>
                        {message.content && (
                          <div dangerouslySetInnerHTML={{
                            __html: message.content
                              .replace(/&/g, "&amp;")
                              .replace(/</g, "&lt;")
                              .replace(/>/g, "&gt;")
                              .replace(/"/g, "&quot;")
                              .replace(/@(\S+)/g, "<span class=\"chat-bubble__mention\">@$1</span>")
                          }} />
                        )}
                      </>
                    )}
                    {(message as any).attachment && (
                      <div className="chat-bubble__attachment"
                        onClick={() => setViewingFile((message as any).attachment)}
                        style={{ cursor: "pointer" }}>
                        {(message as any).attachment.contentType?.startsWith("image/") ? (
                          <img src={(message as any).attachment.url} alt={(message as any).attachment.filename}
                            className="chat-bubble__attachment-img" />
                        ) : (
                          <span className="chat-bubble__attachment-file">
                            📎 {(message as any).attachment.filename} ({((message as any).attachment.size / 1024).toFixed(0)} KB)
                          </span>
                        )}
                      </div>
                    )}
                  </article>
                );
              })
            )}
            <div ref={messageEndRef} />
          </div>

          {/* Function Bar */}
          <div className="function-bar">
            <div style={{ position: "relative" }}>
              <button className={`fn-pill ${showSkillDropdown ? "fn-pill--active" : ""}`}
                onClick={() => { setShowSkillDropdown(!showSkillDropdown); setShowAttrDropdown(false); setShowDicePanel(false); }}
                type="button">🎯 技能检定</button>
              {showSkillDropdown && (
                <div className="fn-dropdown">
                  {isKeeper && (
                    <div className="fn-dropdown__chars">
                      {room.characters?.filter((c) => c.active !== false).map((c) => (
                        <button key={c.id} type="button"
                          className={`fn-dropdown__char-chip${kpCheckCharId === c.id ? " fn-dropdown__char-chip--active" : ""}`}
                          onClick={() => setKpCheckCharId(kpCheckCharId === c.id ? "" : c.id)}>
                          {c.basic?.name || "未命名"}{c.ownerId === memberId ? "(我)" : ""}
                        </button>
                      ))}
                    </div>
                  )}
                  {(isKeeper ? kpCheckCharId : myChar) && (
                    <div className="fn-dropdown__diff">
                      <span style={{ fontSize: "11px", color: "var(--text-muted)" }}>难度:</span>
                      {(["regular", "hard", "extreme"] as const).map((d) => (
                        <button key={d} type="button"
                          className={`fn-pill fn-pill--xs ${checkDifficulty === d ? "fn-pill--active" : ""}`}
                          onClick={() => setCheckDifficulty(d)}>
                          {d === "regular" ? "常规" : d === "hard" ? "困难" : "极难"}
                        </button>
                      ))}
                      {isKeeper && (
                        <label style={{ fontSize: "11px", display: "flex", alignItems: "center", gap: "4px", marginLeft: "8px" }}>
                          <input type="checkbox" checked={hiddenRoll} onChange={(e) => setHiddenRoll(e.target.checked)} />
                          暗投
                        </label>
                      )}
                    </div>
                  )}
                  {(isKeeper && kpCheckCharId
                    ? room.characters?.find((c) => c.id === kpCheckCharId)?.skills.filter((s) => s.value != null)
                    : myChar?.skills.filter((s) => s.value != null)
                  )?.map((skill) => (
                    <button key={skill.name} className="fn-dropdown__item"
                      onClick={() => { structuredCheck("skill", skill.name, skill.value!, checkDifficulty, hiddenRoll && isKeeper); setShowSkillDropdown(false); }}
                      type="button">
                      <span className="fn-dropdown__item-name">{skill.name}</span>
                      <span className="fn-dropdown__item-val">{skill.value}</span>
                      <span className="fn-dropdown__item-sub">{skill.half}/{skill.fifth}</span>
                    </button>
                  ))}
                  {!isKeeper && (!myChar || myChar.skills.filter((s) => s.value != null).length === 0) && (
                    <p style={{ padding: "8px", fontSize: "12px", color: "var(--text-muted)" }}>请先上传角色卡</p>
                  )}
                </div>
              )}
            </div>
            <div style={{ position: "relative" }}>
              <button className={`fn-pill ${showAttrDropdown ? "fn-pill--active" : ""}`}
                onClick={() => { setShowAttrDropdown(!showAttrDropdown); setShowSkillDropdown(false); setShowDicePanel(false); }}
                type="button">📊 属性检定</button>
              {showAttrDropdown && (
                <div className="fn-dropdown">
                  {isKeeper && (
                    <div className="fn-dropdown__chars">
                      {room.characters?.filter((c) => c.active !== false).map((c) => (
                        <button key={c.id} type="button"
                          className={`fn-dropdown__char-chip${kpCheckCharId === c.id ? " fn-dropdown__char-chip--active" : ""}`}
                          onClick={() => setKpCheckCharId(kpCheckCharId === c.id ? "" : c.id)}>
                          {c.basic?.name || "未命名"}{c.ownerId === memberId ? "(我)" : ""}
                        </button>
                      ))}
                    </div>
                  )}
                  {(isKeeper ? kpCheckCharId : myChar) && (
                    <div className="fn-dropdown__diff">
                      <span style={{ fontSize: "11px", color: "var(--text-muted)" }}>难度:</span>
                      {(["regular", "hard", "extreme"] as const).map((d) => (
                        <button key={d} type="button"
                          className={`fn-pill fn-pill--xs ${checkDifficulty === d ? "fn-pill--active" : ""}`}
                          onClick={() => setCheckDifficulty(d)}>
                          {d === "regular" ? "常规" : d === "hard" ? "困难" : "极难"}
                        </button>
                      ))}
                      {isKeeper && (
                        <label style={{ fontSize: "11px", display: "flex", alignItems: "center", gap: "4px", marginLeft: "8px" }}>
                          <input type="checkbox" checked={hiddenRoll} onChange={(e) => setHiddenRoll(e.target.checked)} />
                          暗投
                        </label>
                      )}
                    </div>
                  )}
                  {(isKeeper && kpCheckCharId
                    ? room.characters?.find((c) => c.id === kpCheckCharId)?.attributes.filter((a) => a.value != null)
                    : myChar?.attributes.filter((a) => a.value != null)
                  )?.map((attr) => (
                    <button key={attr.key} className="fn-dropdown__item"
                      onClick={() => { structuredCheck("attr", attr.key, attr.value!, checkDifficulty, hiddenRoll && isKeeper); setShowAttrDropdown(false); }}
                      type="button">
                      <span className="fn-dropdown__item-name">{attr.label} ({attr.key})</span>
                      <span className="fn-dropdown__item-val">{attr.value}</span>
                      <span className="fn-dropdown__item-sub">{attr.half}/{attr.fifth}</span>
                    </button>
                  ))}
                  {!isKeeper && (!myChar || myChar.attributes.filter((a) => a.value != null).length === 0) && (
                    <p style={{ padding: "8px", fontSize: "12px", color: "var(--text-muted)" }}>请先上传角色卡</p>
                  )}
                </div>
              )}
            </div>
            {myChar && myChar.status.san != null && (
              <button className="fn-pill fn-pill--danger"
                onClick={() => setShowSanCheckPanel(true)}
                type="button" title={`SAN: ${myChar.status.san}`}>
                🧠 SAN CHECK ({myChar.status.san})
              </button>
            )}
            <div style={{ position: "relative" }}>
              <button className={`fn-pill ${showDicePanel ? "fn-pill--active" : ""}`}
                onClick={() => { setShowDicePanel(!showDicePanel); setShowSkillDropdown(false); setShowAttrDropdown(false); }}
                type="button">🎲 自由骰子</button>
              {showDicePanel && (
                <div className="fn-dropdown" style={{ minWidth: "300px" }}>
                  <form onSubmit={rollDice} style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
                    <div style={{ display: "flex", gap: "6px", alignItems: "center" }}>
                      <input value={rollLabel} onChange={(e) => setRollLabel(e.target.value)} placeholder="标签" style={{ width: "80px" }} />
                      <input value={expression} onChange={(e) => setExpression(e.target.value)} style={{ width: "70px" }} />
                      <input inputMode="numeric" value={targetValue} onChange={(e) => setTargetValue(e.target.value)} placeholder="目标" style={{ width: "60px" }} />
                      <select value={bonusPenalty} onChange={(e) => setBonusPenalty(e.target.value)} style={{ width: "70px" }}>
                        <option value="2">奖励2</option><option value="1">奖励1</option>
                        <option value="0">无</option><option value="-1">惩罚1</option><option value="-2">惩罚2</option>
                      </select>
                    </div>
                    <div style={{ display: "flex", gap: "4px", flexWrap: "wrap" }}>
                      {["1d100", "1d6", "1d10", "2d6+3"].map((item) => (
                        <button key={item} type="button" className="dice-inline__preset" onClick={() => setExpression(item)}>{item}</button>
                      ))}
                    </div>
                    {isKeeper && (
                      <label style={{ fontSize: "12px", display: "flex", alignItems: "center", gap: "6px" }}>
                        <input type="checkbox" checked={hiddenRoll} onChange={(e) => setHiddenRoll(e.target.checked)} />
                        仅KP可见
                      </label>
                    )}
                    <button className="button button--primary button--sm" type="submit">投掷</button>
                  </form>
                </div>
              )}
            </div>
            {isKeeper && (
              <>
                <div style={{ width: "1px", background: "var(--border)", margin: "0 4px" }} />
                {room.combatState?.active ? (
                  <button className="fn-pill fn-pill--active" onClick={() => setShowCombatPanel(true)} type="button">
                    ⚔️ 战斗 R{room.combatState.roundNumber}
                  </button>
                ) : (
                  <button className="fn-pill" onClick={startCombat} type="button">⚔️ 开始战斗</button>
                )}
                {room.chaseState?.active ? (
                  <button className="fn-pill fn-pill--active" onClick={() => setShowChasePanel(true)} type="button">
                    🏃 追逐
                  </button>
                ) : (
                  <button className="fn-pill" onClick={startChase} type="button">🏃 开始追逐</button>
                )}
              </>
            )}
          </div>

          {/* Composer Bar */}
          <form className={`composer-bar${dragOver ? " composer-bar--drag" : ""}`} onSubmit={sendMessage}
            onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
            onDragLeave={(e) => { e.preventDefault(); setDragOver(false); }}
            onDrop={async (e) => {
              e.preventDefault(); setDragOver(false);
              const file = e.dataTransfer.files?.[0];
              if (!file) return;
              const result = await uploadFile(file);
              if (result) setAttachment(result);
            }}>
            <div className="composer-bar__body">
              {replyTo && (
                <div className="composer-bar__reply">
                  回复 {replyTo.senderName}: {replyTo.content.slice(0, 40)}
                  <button type="button" onClick={() => setReplyTo(null)}>✕</button>
                </div>
              )}
              {attachment && (
                <div className="composer-bar__attachment">
                  {attachment.contentType.startsWith("image/") ? (
                    <img src={attachment.url} alt={attachment.filename} className="composer-bar__attachment-img" />
                  ) : (
                    <span className="composer-bar__attachment-file">📎 {attachment.filename} ({(attachment.size / 1024).toFixed(0)} KB)</span>
                  )}
                  <button type="button" onClick={() => setAttachment(null)}
                    className="composer-bar__attachment-remove" title="移除附件">✕</button>
                </div>
              )}
              <textarea className={`composer-bar__input${dragOver ? " composer-bar__input--drag" : ""}`}
                value={draft} onChange={(e) => setDraft(e.target.value)}
                placeholder={uploading ? "上传中..." : dragOver ? "松开以上传文件" : "输入消息... 也可拖拽文件到这里"}
                rows={8}
              />
            </div>
            <div className="composer-bar__actions">
              <button type="button" className="composer-bar__icon-btn"
                onClick={() => document.getElementById("composer-file-input")?.click()}
                title="上传文件">
                📎
              </button>
              <input type="file" id="composer-file-input" style={{ display: "none" }}
                accept=".png,.jpg,.jpeg,.gif,.webp,.svg,.pdf,.txt,.md,.json,.csv"
                onChange={async (e) => {
                  const file = e.target.files?.[0];
                  if (!file) return;
                  const result = await uploadFile(file);
                  if (result) setAttachment(result);
                  e.target.value = "";
                }} />
              <div className="voice-mode-toggle">
                <button type="button"
                  className={`voice-mode-toggle__btn ${voiceMode === "off" ? "voice-mode-toggle__btn--active" : ""}`}
                  onClick={() => setVoiceMode("off")}>关</button>
                <button type="button"
                  className={`voice-mode-toggle__btn ${voiceMode === "push" ? "voice-mode-toggle__btn--active" : ""}`}
                  onClick={() => setVoiceMode("push")}>按键</button>
                <button type="button"
                  className={`voice-mode-toggle__btn ${voiceMode === "voice" ? "voice-mode-toggle__btn--active" : ""}`}
                  onClick={() => setVoiceMode("voice")}>自动</button>
              </div>
              <VoiceRecorder roomId={room.id} memberId={memberId!} />
              <button className="button button--primary" type="submit" disabled={uploading}>
                {uploading ? "上传中..." : "发送"}
              </button>
            </div>
          </form>
        </div>


        {/* Right Panel */}
        <aside className="right-panel">
          <div className="right-panel__kp">
            <div className="right-panel__kp-name">
              {room.members.find((m) => m.role === "keeper")?.displayName || "KP"}
            </div>
            <div className="right-panel__kp-status">
              <span className="right-panel__kp-dot right-panel__kp-dot--online" />
              {room.name}
            </div>
          </div>
          {currentMember && (
            <div style={{ padding: "8px", borderBottom: "1px solid var(--border)" }}>
              <VoiceRoom roomId={room.id} memberId={memberId || ""} memberName={currentMember?.displayName || ""}
                memberNames={Object.fromEntries(room.members.map((m) => [m.id, m.displayName]))} />
            </div>
          )}
          <div className="right-panel__members">
            {/* KP card */}
            {(() => {
              const kpMember = room.members.find((m) => m.role === "keeper");
              const kpChar = kpMember ? findMemberChar(kpMember.id, room.characters) : undefined;
              if (!kpMember) return null;
              return (
                <div key={kpMember.id}
                  className="player-mini-card"
                  onClick={() => { if (kpChar) setSelectedCharId(selectedCharId === kpChar.id ? null : kpChar.id); }}>
                  <div className="player-mini-card__header">
                    <div className="player-mini-card__avatar"
                      style={{ color: "var(--warning)" }}>
                      {kpMember.displayName.charAt(0)}
                    </div>
                    <div>
                      <div className="player-mini-card__name">KP · {kpMember.displayName}</div>
                      <div className="player-mini-card__player">
                        {kpMember.online ? "在线" : "离线"}
                      </div>
                    </div>
                  </div>
                </div>
              );
            })()}
            {/* Separator */}
            <div style={{ borderTop: "1px solid var(--border)", margin: "6px 8px" }} />
            {/* Player cards */}
            {room.members.filter((m) => m.role === "player").map((member) => {
              const char = findMemberChar(member.id, room.characters);
              return (
                <div key={member.id}
                  className={`player-mini-card ${!char ? "player-mini-card--npc" : ""}`}
                  onClick={() => { if (char) setSelectedCharId(selectedCharId === char.id ? null : char.id); }}>
                  <div className="player-mini-card__header">
                    <div className="player-mini-card__avatar">
                      {(char?.basic?.name || member.displayName).charAt(0)}
                    </div>
                    <div>
                      <div className="player-mini-card__name">{char?.basic?.name || member.displayName}</div>
                      <div className="player-mini-card__player">
                        {member.displayName} {member.online ? "在线" : "离线"}
                      </div>
                    </div>
                  </div>
                  {char && (
                    <div className="player-mini-card__stats">
                      {char.status.hp != null && (
                        <div className="player-mini-card__stat">
                          <span className="player-mini-card__stat-label">HP</span>
                          <span className="player-mini-card__stat-val" style={{ color: "var(--error)" }}>
                            {char.initialStatus?.hp != null ? `${char.initialStatus.hp}/` : ""}{char.status.hp}
                          </span>
                          <div className="player-mini-card__stat-bar">
                            <div className="player-mini-card__stat-fill" style={{
                              width: char.initialStatus?.hp && typeof char.status.hp === "number" ?
                                `${Math.min((char.status.hp / (char.initialStatus.hp || 1)) * 100, 100)}%` : "60%",
                              background: "var(--error)" }} />
                          </div>
                        </div>
                      )}
                      {char.status.san != null && (
                        <div className="player-mini-card__stat">
                          <span className="player-mini-card__stat-label">SAN</span>
                          <span className="player-mini-card__stat-val" style={{ color: "#7C6FF7" }}>
                            {char.initialStatus?.san != null ? `${char.initialStatus.san}/` : ""}{char.status.san}
                          </span>
                          <div className="player-mini-card__stat-bar">
                            <div className="player-mini-card__stat-fill" style={{
                              width: char.initialStatus?.san && typeof char.status.san === "number" ?
                                `${Math.min((char.status.san / (char.initialStatus.san || 1)) * 100, 100)}%` : "60%",
                              background: "#7C6FF7" }} />
                          </div>
                        </div>
                      )}
                      {char.status.mp != null && (
                        <div className="player-mini-card__stat">
                          <span className="player-mini-card__stat-label">MP</span>
                          <span className="player-mini-card__stat-val" style={{ color: "#4FC3F7" }}>
                            {char.initialStatus?.mp != null ? `${char.initialStatus.mp}/` : ""}{char.status.mp}
                          </span>
                          <div className="player-mini-card__stat-bar">
                            <div className="player-mini-card__stat-fill" style={{
                              width: char.initialStatus?.mp && typeof char.status.mp === "number" ?
                                `${Math.min((char.status.mp / (char.initialStatus.mp || 1)) * 100, 100)}%` : "60%",
                              background: "#4FC3F7" }} />
                          </div>
                        </div>
                      )}
                    </div>
                  )}
                  {member.role !== "keeper" && !char && (
                    <p style={{ fontSize: "11px", color: "var(--text-muted)", textAlign: "center", padding: "4px" }}>未上传角色卡</p>
                  )}
                </div>
              );
            })}
          </div>
        </aside>
      </div>

      {/* SAN Check Panel */}
      {showSanCheckPanel && myChar && (
        <SanCheckPanel roomId={room.id} character={myChar} isKeeper={isKeeper}
          onClose={() => setShowSanCheckPanel(false)} />
      )}

      {/* Combat Panel */}
      {showCombatPanel && room.combatState && (
        <CombatPanel roomId={room.id} memberId={memberId!} combat={room.combatState}
          characters={room.characters || []} isKeeper={isKeeper}
          onClose={() => setShowCombatPanel(false)} />
      )}

      {/* Chase Panel */}
      {showChasePanel && room.chaseState && (
        <ChasePanel roomId={room.id} memberId={memberId!} chase={room.chaseState}
          characters={room.characters || []} isKeeper={isKeeper}
          onClose={() => setShowChasePanel(false)} />
      )}

      {/* File Viewer Modal */}
      {viewingFile && (
        <div className="modal-overlay" onClick={() => setViewingFile(null)}>
          <div className="modal-panel" onClick={(e) => e.stopPropagation()} style={{ maxWidth: "90vw", maxHeight: "90vh", display: "flex", flexDirection: "column" }}>
            <div className="modal-panel__header">
              <span className="modal-panel__title" style={{ fontSize: "14px", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                {viewingFile.filename}
              </span>
              <div style={{ display: "flex", gap: "8px", alignItems: "center" }}>
                <a href={viewingFile.url} download={viewingFile.filename}
                  className="button button--ghost button--sm" style={{ textDecoration: "none" }}>
                  下载
                </a>
                <button className="button button--ghost button--sm" onClick={() => setViewingFile(null)} type="button">✕</button>
              </div>
            </div>
            <div style={{ flex: 1, overflow: "auto", display: "flex", justifyContent: "center", alignItems: "flex-start" }}>
              {viewingFile.contentType.startsWith("image/") ? (
                <img src={viewingFile.url} alt={viewingFile.filename}
                  style={{ maxWidth: "100%", maxHeight: "75vh", objectFit: "contain" }} />
              ) : viewingFile.contentType === "application/pdf" ? (
                <iframe src={viewingFile.url} style={{ width: "100%", height: "80vh", border: "none" }} title={viewingFile.filename} />
              ) : viewingFile.contentType.startsWith("text/") || viewingFile.contentType === "application/json" ? (
                <FileContentViewer url={viewingFile.url} />
              ) : (
                <div style={{ padding: "40px", textAlign: "center", color: "var(--text-secondary)" }}>
                  <p style={{ fontSize: "32px", marginBottom: "12px" }}>📄</p>
                  <p>{viewingFile.filename}</p>
                  <p style={{ fontSize: "12px", color: "var(--text-muted)" }}>此文件类型暂不支持在线预览</p>
                  <a href={viewingFile.url} download={viewingFile.filename}
                    className="button button--primary button--sm" style={{ marginTop: "12px", display: "inline-block", textDecoration: "none" }}>
                    下载文件
                  </a>
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* KP Leave Confirmation */}
      {showKpLeaveConfirm && (
        <div className="modal-overlay" onClick={() => setShowKpLeaveConfirm(false)}>
          <div className="modal-panel" onClick={(e) => e.stopPropagation()} style={{ maxWidth: "380px", textAlign: "center" }}>
            <p style={{ fontSize: "15px", color: "var(--text)", margin: "0 0 8px", fontWeight: 600 }}>
              确定要离开房间吗
            </p>
            <p style={{ fontSize: "13px", color: "var(--text-muted)", margin: "0 0 20px" }}>
              之前的记录均不会保存
            </p>
            <div style={{ display: "flex", gap: "10px", justifyContent: "center" }}>
              <button className="button button--ghost" style={{ borderRadius: "12px", padding: "8px 32px" }}
                onClick={leaveLocalRoom} type="button" disabled={leaving}>
                {leaving ? "退出中..." : "确定"}
              </button>
              <button className="button button--danger" style={{ borderRadius: "12px", padding: "8px 32px" }}
                onClick={() => setShowKpLeaveConfirm(false)} type="button" disabled={leaving}>
                取消
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Delete Message Confirmation */}
      {deleteMsgId && (
        <div className="modal-overlay" onClick={() => !deleting && setDeleteMsgId(null)}>
          <div className="modal-panel" onClick={(e) => e.stopPropagation()} style={{ maxWidth: "380px", textAlign: "center" }}>
            <p style={{ fontSize: "15px", color: "var(--text)", margin: "0 0 8px", fontWeight: 600 }}>
              确定要删除这条消息吗
            </p>
            <p style={{ fontSize: "13px", color: "var(--text-muted)", margin: "0 0 20px" }}>
              删除后无法恢复
            </p>
            <div style={{ display: "flex", gap: "10px", justifyContent: "center" }}>
              <button className="button button--ghost" style={{ borderRadius: "12px", padding: "8px 32px" }}
                onClick={deleteMessage} type="button" disabled={deleting}>
                {deleting ? "删除中..." : "确定"}
              </button>
              <button className="button button--danger" style={{ borderRadius: "12px", padding: "8px 32px" }}
                onClick={() => setDeleteMsgId(null)} type="button" disabled={deleting}>
                取消
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Delete NPC Confirmation */}
      {deleteNpcId && (
        <div className="modal-overlay" onClick={() => !deletingNpc && setDeleteNpcId(null)}>
          <div className="modal-panel" onClick={(e) => e.stopPropagation()} style={{ maxWidth: "380px", textAlign: "center" }}>
            <p style={{ fontSize: "15px", color: "var(--text)", margin: "0 0 8px", fontWeight: 600 }}>
              确定要删除这个 NPC 角色卡吗
            </p>
            <p style={{ fontSize: "13px", color: "var(--text-muted)", margin: "0 0 20px" }}>
              删除后无法恢复
            </p>
            <div style={{ display: "flex", gap: "10px", justifyContent: "center" }}>
              <button className="button button--ghost" style={{ borderRadius: "12px", padding: "8px 32px" }}
                onClick={deleteNpc} type="button" disabled={deletingNpc}>
                {deletingNpc ? "删除中..." : "确定"}
              </button>
              <button className="button button--danger" style={{ borderRadius: "12px", padding: "8px 32px" }}
                onClick={() => setDeleteNpcId(null)} type="button" disabled={deletingNpc}>
                取消
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Character Card Drawer */}
      {selectedChar && (
        <div className="modal-overlay" onClick={() => setSelectedCharId(null)}>
          <div className="drawer" onClick={(e) => e.stopPropagation()}>
            <div className="drawer__header">
              <span className="drawer__title">角色卡</span>
              <button className="button button--ghost button--sm" onClick={() => setSelectedCharId(null)} type="button">?</button>
            </div>
            <CharacterCardView canEdit={isKeeper} canRoll={Boolean(currentMember) && selectedChar.active !== false}
              character={selectedChar} onRoll={rollCharacterCheck} onUpdate={updateCharacter} />
          </div>
        </div>
      )}
    </div>
  );
}

function DiceRollView({ roll }: { roll: DiceRollResult }) {
  // Backend strips total/breakdown for non-KP members on hidden rolls
  const hiddenFromViewer = roll.hidden && roll.total == null;
  if (hiddenFromViewer) {
    return (
      <div className="chat-roll-result">
        <div className="chat-roll-result__dice">?</div>
        <div>
          <span className="chat-roll-result__label">暗骰</span>
          <div className="chat-roll-result__detail">仅KP可见</div>
        </div>
      </div>
    );
  }
  const detail = roll.breakdown.map((item) => {
    if (item.kind === "coc_d100" && item.tensRolls) {
      return `[${item.tensRolls.join(", ")}][${item.ones}]`;
    }
    const modifier = item.modifier ? ` ${item.modifier > 0 ? "+" : ""}${item.modifier}` : "";
    return `${item.count}d${item.sides}: [${item.rolls.join(", ")}]${modifier}`;
  }).join(" | ");
  return (
    <div className="chat-roll-result">
      <div className="chat-roll-result__dice">{roll.total}</div>
      <div>
        <span className="chat-roll-result__label">{roll.label || roll.expression}</span>
        {roll.hidden && <span style={{ fontSize: "10px", color: "var(--error)", marginLeft: "4px" }}>暗投</span>}
        {roll.successLabel && (
          <span className={roll.isSuccess ? "chat-roll-result__success" : "chat-roll-result__fail"}>
            {" "}{roll.successLabel}
          </span>
        )}
        <div className="chat-roll-result__detail">
          {detail}{roll.targetValue ? `  目标 ${roll.targetValue}` : ""}
        </div>
      </div>
    </div>
  );
}

function FileContentViewer({ url }: { url: string }) {
  const [text, setText] = useState<string | null>(null);
  const [error, setError] = useState(false);
  useEffect(() => {
    fetch(url).then(r => r.text()).then(setText).catch(() => setError(true));
  }, [url]);
  if (error) return <p style={{ padding: "20px", color: "var(--text-muted)" }}>无法加载文件内容</p>;
  if (text === null) return <p style={{ padding: "20px", color: "var(--text-muted)" }}>加载中...</p>;
  return (
    <pre style={{
      width: "100%", maxHeight: "75vh", overflow: "auto", padding: "16px",
      background: "var(--bg)", color: "var(--text)", fontSize: "13px",
      lineHeight: 1.6, borderRadius: "var(--radius)", margin: 0,
      whiteSpace: "pre-wrap", wordBreak: "break-word",
    }}>{text}</pre>
  );
}

function formatTime(value: string) {
  return new Intl.DateTimeFormat("zh-CN", { hour: "2-digit", minute: "2-digit" }).format(new Date(value));
}
