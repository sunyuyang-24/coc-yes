"use client";

import type { FormEvent } from "react";
import { useEffect, useMemo, useRef, useState } from "react";
import type { RoomDetail } from "@coc-yes/shared";
import { apiRequest, wsUrl } from "@/lib/api";

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

export function RoomConsole() {
  const [room, setRoom] = useState<RoomDetail | null>(null);
  const [memberId, setMemberId] = useState<string | null>(null);
  const [roomName, setRoomName] = useState("雾港第一夜");
  const [keeperName, setKeeperName] = useState("KP");
  const [inviteCode, setInviteCode] = useState("");
  const [playerName, setPlayerName] = useState("调查员");
  const [draft, setDraft] = useState("");
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
              <h2>{room.name}</h2>
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
                    <small>{member.role === "keeper" ? "KP" : "玩家"}</small>
                  </div>
                </div>
              ))}
            </div>

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
                  <p>{message.content}</p>
                </article>
              ))}
              <div ref={messageEndRef} />
            </div>

            <form className="composer" onSubmit={sendMessage}>
              <input
                value={draft}
                onChange={(event) => setDraft(event.target.value)}
                placeholder="输入跑团消息、线索或 KP 描述..."
              />
              <button className="button button--primary" type="submit">
                发送
              </button>
            </form>
          </section>
        </div>
      ) : null}
    </section>
  );
}

function formatTime(value: string) {
  return new Intl.DateTimeFormat("zh-CN", {
    hour: "2-digit",
    minute: "2-digit"
  }).format(new Date(value));
}
