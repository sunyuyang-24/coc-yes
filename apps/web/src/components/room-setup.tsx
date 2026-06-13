"use client";

import type { FormEvent } from "react";
import type { RoomDetail, UserInfo } from "@coc-yes/shared";
import { apiRequest } from "@/lib/api";
import { clearAuth } from "@/lib/auth";
import { LoginPanel } from "@/components/login-panel";

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
  if (!isLoggedIn) {
    return <LoginPanel onAuth={() => setIsLoggedIn(true)} />;
  }

  return (
    <section className="setup-screens">
      {/* My Rooms */}
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

      <CreateRoomForm
        roomName={roomName} setRoomName={setRoomName}
        keeperName={keeperName} setKeeperName={setKeeperName}
        roomPassword={roomPassword} setRoomPassword={setRoomPassword}
        onCreate={createRoom}
      />
      <JoinRoomForm
        inviteCode={inviteCode} setInviteCode={setInviteCode}
        playerName={playerName} setPlayerName={setPlayerName}
        joinPassword={joinPassword} setJoinPassword={setJoinPassword}
        joinAsSpectator={joinAsSpectator} setJoinAsSpectator={setJoinAsSpectator}
        onJoin={joinRoom}
      />
    </section>
  );
}

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
