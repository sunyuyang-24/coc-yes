"use client";

import { type FormEvent, useCallback, useEffect, useRef, useState } from "react";
import type { RoomDetail, UserInfo } from "@coc-yes/shared";
import { apiRequest } from "@/lib/api";
import { clearAuth, login, register } from "@/lib/auth";

type MyRoom = { id: string; name: string; status: string; createdAt: string; inviteCode: string };

type Props = {
  isLoggedIn: boolean;
  setIsLoggedIn: (v: boolean) => void;
  currentUser: UserInfo | null;
  myRooms: MyRoom[];
  loadingRooms: boolean;
  setMyRooms: (rooms: MyRoom[]) => void;
  setLoadingRooms: (v: boolean) => void;
  roomName: string; setRoomName: (v: string) => void;
  keeperName: string; setKeeperName: (v: string) => void;
  roomPassword: string; setRoomPassword: (v: string) => void;
  joinPassword: string; setJoinPassword: (v: string) => void;
  joinAsSpectator: boolean; setJoinAsSpectator: (v: boolean) => void;
  inviteCode: string; setInviteCode: (v: string) => void;
  playerName: string; setPlayerName: (v: string) => void;
  enterRoom: (room: RoomDetail, memberId: string) => void;
  setRoom: (room: RoomDetail | null) => void;
  setMemberId: (id: string | null) => void;
  setNotice: (msg: string) => void;
  createRoom: (e: FormEvent<HTMLFormElement>) => Promise<void>;
  joinRoom: (e: FormEvent<HTMLFormElement>) => Promise<void>;
  onDeleteRoom: (roomId: string) => Promise<void>;
};

export function RoomSetup({
  isLoggedIn, setIsLoggedIn, currentUser, myRooms, loadingRooms,
  setMyRooms, setLoadingRooms, roomName, setRoomName, keeperName, setKeeperName,
  roomPassword, setRoomPassword, joinPassword, setJoinPassword,
  joinAsSpectator, setJoinAsSpectator, inviteCode, setInviteCode,
  playerName, setPlayerName, enterRoom, setRoom, setMemberId,
  setNotice, createRoom, joinRoom, onDeleteRoom,
}: Props) {
  return (
    <div style={{
      display: "flex", gap: "24px", width: "100%", maxWidth: "1080px",
      margin: "60px auto 40px", padding: "0 24px", boxSizing: "border-box",
    }}>
      <div style={{ flex: 1, minWidth: 0 }}>
        {/* Column 1: Player / Login */}
        {isLoggedIn ? (
          <PlayerCard
            currentUser={currentUser}
            myRooms={myRooms}
            loadingRooms={loadingRooms}
            setMyRooms={setMyRooms}
            setLoadingRooms={setLoadingRooms}
            setIsLoggedIn={setIsLoggedIn}
            enterRoom={enterRoom}
            setRoom={setRoom}
            setMemberId={setMemberId}
            onDeleteRoom={onDeleteRoom}
          />
        ) : (
          <LoginCard onAuth={() => setIsLoggedIn(true)} />
        )}
      </div>
      <div style={{ flex: 1, minWidth: 0 }}>
        {/* Column 2: Create Room */}
        <CreateRoomForm
          roomName={roomName} setRoomName={setRoomName}
          keeperName={keeperName} setKeeperName={setKeeperName}
          roomPassword={roomPassword} setRoomPassword={setRoomPassword}
          onCreate={createRoom}
        />
      </div>
      <div style={{ flex: 1, minWidth: 0 }}>
        {/* Column 3: Join Room */}
        <JoinRoomForm
          inviteCode={inviteCode} setInviteCode={setInviteCode}
          playerName={playerName} setPlayerName={setPlayerName}
          joinPassword={joinPassword} setJoinPassword={setJoinPassword}
          joinAsSpectator={joinAsSpectator} setJoinAsSpectator={setJoinAsSpectator}
          onJoin={joinRoom}
        />
      </div>
    </div>
  );
}

/* ---- Column 1: Player Card (logged in) ---- */

function ConfirmModal({
  title, message, confirmLabel, onConfirm, onCancel, loading,
}: {
  title: string; message: React.ReactNode; confirmLabel: string;
  onConfirm: () => void; onCancel: () => void; loading?: boolean;
}) {
  return (
    <div className="modal-overlay" onClick={onCancel}>
      <div className="modal-panel" onClick={(e) => e.stopPropagation()} style={{ maxWidth: "360px", padding: "24px" }}>
        <div style={{ fontSize: "14px", color: "var(--text)", marginBottom: "8px", fontWeight: 500 }}>{title}</div>
        <div style={{ fontSize: "13px", color: "var(--text-muted)", marginBottom: "20px", lineHeight: 1.6 }}>{message}</div>
        <div style={{ display: "flex", gap: "8px", justifyContent: "flex-end" }}>
          <button className="button button--ghost button--sm" onClick={onConfirm} disabled={loading} type="button">
            {loading ? `${confirmLabel}中...` : confirmLabel}
          </button>
          <button className="button button--danger button--sm" onClick={onCancel} type="button">取消</button>
        </div>
      </div>
    </div>
  );
}

function PlayerCard({
  currentUser, myRooms, loadingRooms, setMyRooms, setLoadingRooms,
  setIsLoggedIn, enterRoom, setRoom, setMemberId, onDeleteRoom,
}: {
  currentUser: UserInfo | null;
  myRooms: MyRoom[];
  loadingRooms: boolean;
  setMyRooms: (rooms: MyRoom[]) => void;
  setLoadingRooms: (v: boolean) => void;
  setIsLoggedIn: (v: boolean) => void;
  enterRoom: (room: RoomDetail, memberId: string) => void;
  setRoom: (room: RoomDetail | null) => void;
  setMemberId: (id: string | null) => void;
  onDeleteRoom: (roomId: string) => Promise<void>;
}) {
  const [deleteTarget, setDeleteTarget] = useState<MyRoom | null>(null);
  const [deleting, setDeleting] = useState(false);
  const [showLogoutConfirm, setShowLogoutConfirm] = useState(false);
  const enteringRef = useRef(false);

  const fetchMyRooms = useCallback(() => {
    setLoadingRooms(true);
    apiRequest<{ rooms: MyRoom[] }>("/api/rooms/mine")
      .then(data => setMyRooms(data.rooms))
      .catch(() => {})
      .finally(() => setLoadingRooms(false));
  }, [setLoadingRooms, setMyRooms]);

  useEffect(() => { fetchMyRooms(); }, [fetchMyRooms]);

  function handleLogout() {
    clearAuth();
    setIsLoggedIn(false);
  }

  async function handleDelete() {
    if (!deleteTarget) return;
    setDeleting(true);
    try {
      await onDeleteRoom(deleteTarget.id);
      setMyRooms(myRooms.filter(r => r.id !== deleteTarget.id));
    } catch { /* keep room in list, user can retry */ }
    setDeleting(false);
    setDeleteTarget(null);
  }

  async function handleEnterRoom(r: MyRoom) {
    if (enteringRef.current) return;
    enteringRef.current = true;
    try {
      if (r.status !== "ended") {
        const joinData = await apiRequest<{ room: RoomDetail; currentMemberId: string }>(
          `/api/rooms/join`, { method: "POST", body: JSON.stringify({
            invite_code: r.inviteCode,
            display_name: currentUser?.display_name || currentUser?.username || "",
            role: "player",
          })});
        enterRoom(joinData.room, joinData.currentMemberId);
      } else {
        const data = await apiRequest<{ room: RoomDetail }>(`/api/rooms/${r.id}`);
        setRoom(data.room);
        setMemberId("");
      }
    } catch { /* join/view failed — user can retry */ }
    enteringRef.current = false;
  }

  return (
    <div className="setup-card">
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <div>
          <p className="panel__kicker">已登录</p>
          <h2>{currentUser?.display_name || currentUser?.username || "玩家"}</h2>
        </div>
        <button className="button button--ghost button--sm" onClick={() => setShowLogoutConfirm(true)} type="button">
          退出
        </button>
      </div>

      <div style={{ marginTop: "16px" }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "8px" }}>
          <span style={{ fontSize: "13px", color: "var(--text-muted)", fontWeight: 500 }}>房间历史</span>
          <button className="button button--ghost button--sm" onClick={fetchMyRooms} type="button" title="刷新">
            {loadingRooms ? "..." : "↻"}
          </button>
        </div>

        {myRooms.length === 0 && !loadingRooms && (
          <div style={{ fontSize: "13px", color: "var(--text-muted)", padding: "12px 0", textAlign: "center" }}>
            暂无历史房间
          </div>
        )}
        {loadingRooms && myRooms.length === 0 && (
          <div style={{ fontSize: "13px", color: "var(--text-muted)", padding: "12px 0", textAlign: "center" }}>
            加载中...
          </div>
        )}

        {myRooms.length > 0 && (
          <div style={{ display: "flex", flexDirection: "column", gap: "6px", maxHeight: "280px", overflowY: "auto" }}>
            {myRooms.map((r) => (
              <div key={r.id} style={{
                display: "flex", justifyContent: "space-between", alignItems: "center",
                padding: "8px 12px", borderRadius: "8px", border: "1px solid var(--border)",
                background: "var(--bg-hover)", fontSize: "13px", position: "relative",
              }}>
                <button
                  className="button--reset"
                  onClick={() => handleEnterRoom(r)}
                  style={{ flexDirection: "column", alignItems: "flex-start", gap: "2px", flex: 1, minWidth: 0, color: "var(--text)" }}
                >
                  <span style={{ fontWeight: 500, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", maxWidth: "100%" }}>{r.name}</span>
                  <span style={{ color: "var(--text-muted)", fontSize: "11px" }}>
                    {r.status === "active" ? "进行中" : r.status === "preparing" ? "准备中" : "已结束"}
                  </span>
                </button>
                <button
                  className="button button--ghost button--sm"
                  onClick={(e) => { e.stopPropagation(); setDeleteTarget(r); }}
                  type="button"
                  title="删除此记录"
                  style={{ position: "absolute", top: "4px", right: "4px", fontSize: "14px", lineHeight: 1, padding: "2px 6px" }}
                >
                  ×
                </button>
              </div>
            ))}
          </div>
        )}
      </div>

      {showLogoutConfirm && (
        <ConfirmModal
          title="退出登录"
          message={<>
            确定要退出登录吗？<br />
            <span style={{ color: "var(--danger)" }}>当前会话将丢失，房间记录仍会保留在服务器上。</span>
          </>}
          confirmLabel="确定"
          onConfirm={handleLogout}
          onCancel={() => setShowLogoutConfirm(false)}
        />
      )}

      {deleteTarget && (
        <ConfirmModal
          title="删除房间记录"
          message={<>
            确定要删除「{deleteTarget.name}」的历史记录吗？<br />
            <span style={{ color: "var(--danger)" }}>此操作不可恢复。</span>
          </>}
          confirmLabel="确定"
          onConfirm={handleDelete}
          onCancel={() => setDeleteTarget(null)}
          loading={deleting}
        />
      )}
    </div>
  );
}

/* ---- Column 1: Login Card (not logged in) ---- */

function LoginCard({ onAuth }: { onAuth: () => void }) {
  const [mode, setMode] = useState<"login" | "register">("login");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      if (mode === "register") {
        await register(username, password, displayName || username);
      } else {
        await login(username, password);
      }
      onAuth();
    } catch (err) {
      setError(err instanceof Error ? err.message : "认证失败");
    } finally {
      setLoading(false);
    }
  }

  return (
    <form className="setup-card" onSubmit={handleSubmit}>
      <p className="panel__kicker">◈ 玩家</p>
      <h2>{mode === "login" ? "登录" : "注册"}</h2>
      <p className="setup-card__desc">
        {mode === "login" ? "登录以查看历史房间" : "创建账号以保存游戏记录"}
      </p>

      <div style={{ display: "flex", borderRadius: "8px", overflow: "hidden", border: "1px solid var(--border)", marginBottom: "16px" }}>
        <button type="button" onClick={() => { setMode("login"); setError(""); }} style={{
          flex: 1, padding: "6px", border: "none", cursor: "pointer", fontSize: "13px",
          background: mode === "login" ? "var(--accent)" : "var(--bg-hover)",
          color: mode === "login" ? "#fff" : "var(--text-muted)",
        }}>
          登录
        </button>
        <button type="button" onClick={() => { setMode("register"); setError(""); }} style={{
          flex: 1, padding: "6px", border: "none", cursor: "pointer", fontSize: "13px",
          background: mode === "register" ? "var(--accent)" : "var(--bg-hover)",
          color: mode === "register" ? "#fff" : "var(--text-muted)",
        }}>
          注册
        </button>
      </div>

      <div className="setup-card__fields">
        <label>用户名
          <input type="text" value={username} onChange={(e) => setUsername(e.target.value)} required
            minLength={2} maxLength={32} autoComplete="username" />
        </label>
        <label>密码
          <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} required
            minLength={4} maxLength={128} autoComplete={mode === "register" ? "new-password" : "current-password"} />
        </label>
        {mode === "register" && (
          <label>显示名称
            <input type="text" value={displayName} onChange={(e) => setDisplayName(e.target.value)}
              minLength={1} maxLength={64} placeholder="可选，默认与用户名相同" />
          </label>
        )}
      </div>

      {error && (
        <p style={{ color: "var(--danger)", fontSize: "13px", margin: "12px 0 0 0", textAlign: "center" }}>{error}</p>
      )}

      <div className="setup-card__actions">
        <button className="button button--primary" type="submit" disabled={loading}>
          {loading ? "处理中..." : mode === "register" ? "注册并登录" : "登录"}
        </button>
      </div>
    </form>
  );
}

/* ---- Column 2: Create Room ---- */

function CreateRoomForm({ roomName, setRoomName, keeperName, setKeeperName, roomPassword, setRoomPassword, onCreate }: {
  roomName: string; setRoomName: (v: string) => void;
  keeperName: string; setKeeperName: (v: string) => void;
  roomPassword: string; setRoomPassword: (v: string) => void;
  onCreate: (e: FormEvent<HTMLFormElement>) => Promise<void>;
}) {
  return (
    <form className="setup-card" onSubmit={onCreate}>
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
  );
}

/* ---- Column 3: Join Room ---- */

function JoinRoomForm({ inviteCode, setInviteCode, playerName, setPlayerName, joinPassword, setJoinPassword, joinAsSpectator, setJoinAsSpectator, onJoin }: {
  inviteCode: string; setInviteCode: (v: string) => void;
  playerName: string; setPlayerName: (v: string) => void;
  joinPassword: string; setJoinPassword: (v: string) => void;
  joinAsSpectator: boolean; setJoinAsSpectator: (v: boolean) => void;
  onJoin: (e: FormEvent<HTMLFormElement>) => Promise<void>;
}) {
  return (
    <form className="setup-card" onSubmit={onJoin}>
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
  );
}
