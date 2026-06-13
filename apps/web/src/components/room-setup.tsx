"use client";

import type { FormEvent, MouseEvent } from "react";
import { useState } from "react";
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
};

export function RoomSetup({
  isLoggedIn, setIsLoggedIn, currentUser, myRooms, loadingRooms,
  setMyRooms, setLoadingRooms, roomName, setRoomName, keeperName, setKeeperName,
  roomPassword, setRoomPassword, joinPassword, setJoinPassword,
  joinAsSpectator, setJoinAsSpectator, inviteCode, setInviteCode,
  playerName, setPlayerName, enterRoom, setRoom, setMemberId,
  setNotice, createRoom, joinRoom,
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

function PlayerCard({
  currentUser, myRooms, loadingRooms, setMyRooms, setLoadingRooms,
  setIsLoggedIn, enterRoom, setRoom, setMemberId,
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
}) {
  return (
    <div className="setup-card">
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <div>
          <p className="panel__kicker">已登录</p>
          <h2>{currentUser?.display_name || currentUser?.username || "玩家"}</h2>
        </div>
        <button className="button button--ghost button--sm" onClick={() => { clearAuth(); setIsLoggedIn(false); }} type="button">
          退出
        </button>
      </div>
      <div style={{ marginTop: "12px" }}>
        <button className="button button--ghost button--sm" onClick={async () => {
          setLoadingRooms(true);
          try {
            const data = await apiRequest<{ rooms: MyRoom[] }>("/api/rooms/mine");
            setMyRooms(data.rooms);
          } catch { /* ignore */ }
          setLoadingRooms(false);
        }} type="button">
          {loadingRooms ? "加载中..." : "我的房间"}
        </button>
      </div>
      {myRooms.length > 0 && (
        <div style={{ marginTop: "8px", display: "flex", flexDirection: "column", gap: "6px" }}>
          {myRooms.map((r) => (
            <div key={r.id} style={{
              display: "flex", justifyContent: "space-between", alignItems: "center",
              padding: "8px 12px", borderRadius: "8px", border: "1px solid var(--border)",
              background: "var(--bg-hover)", fontSize: "13px",
            }}>
              <div>
                <span style={{ color: "var(--text)", fontWeight: 500 }}>{r.name}</span>
                <span style={{ color: "var(--text-muted)", marginLeft: "8px" }}>
                  {r.status === "active" ? "进行中" : r.status === "preparing" ? "准备中" : "已结束"}
                </span>
              </div>
              <button className="button button--ghost button--sm" onClick={async () => {
                try {
                  const data = await apiRequest<{ room: RoomDetail }>(`/api/rooms/${r.id}`);
                  if (data.room.status !== "ended") {
                    const joinData = await apiRequest<{ room: RoomDetail; currentMemberId: string }>(
                      `/api/rooms/join`, { method: "POST", body: JSON.stringify({
                        invite_code: r.inviteCode,
                        display_name: currentUser?.display_name || currentUser?.username || "",
                        role: "player",
                      })});
                    enterRoom(joinData.room, joinData.currentMemberId);
                  } else {
                    setRoom(data.room);
                    setMemberId("");
                  }
                } catch { /* ignore */ }
              }} type="button">
                进入
              </button>
            </div>
          ))}
        </div>
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
