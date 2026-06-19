"use client";

import { type FormEvent, useCallback, useEffect, useState } from "react";
import { apiRequest } from "@/lib/api";
import { clearAuth, getUser, login } from "@/lib/auth";
import type { CharacterCard, UserInfo } from "@coc-yes/shared";
import { ATTRIBUTE_LABELS, ROOM_STATUS_LABELS, ROLE_LABELS, STATUS_LABELS } from "@coc-yes/shared";
import { CharacterDetailModal } from "@/components/character-detail-modal";

type AdminUser = {
  id: string;
  username: string;
  display_name: string;
  created_at: string;
  is_admin: boolean;
  room_count: number;
  character_count: number;
};

type UserRoom = {
  room_id: string;
  room_name: string;
  status: string;
  invite_code: string;
  role: string;
  member_name: string;
  joined_at: string;
  created_at: string;
  ended_at: string | null;
};

type UserChar = {
  id: string;
  name: string;
  source_filename: string;
  created_at: string;
  updated_at: string;
};

export default function AdminPage() {
  const [user, setUser] = useState<UserInfo | null>(null);
  const [loading, setLoading] = useState(true);
  const [loginLoading, setLoginLoading] = useState(false);
  const [loginError, setLoginError] = useState("");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [usersLoading, setUsersLoading] = useState(false);
  const [selectedUser, setSelectedUser] = useState<AdminUser | null>(null);
  const [userRooms, setUserRooms] = useState<UserRoom[]>([]);
  const [userChars, setUserChars] = useState<UserChar[]>([]);
  const [loadingDetail, setLoadingDetail] = useState<"rooms" | "chars" | null>(null);
  const [activeTab, setActiveTab] = useState<"rooms" | "chars">("rooms");
  const [deletingRoomId, setDeletingRoomId] = useState<string | null>(null);
  const [deleteConfirm, setDeleteConfirm] = useState<{ roomId: string; roomName: string } | null>(null);
  const [charDetail, setCharDetail] = useState<CharacterCard | null>(null);
  const [charDetailLoading, setCharDetailLoading] = useState(false);
  const [actionError, setActionError] = useState("");

  useEffect(() => {
    const u = getUser();
    setUser(u);
    setLoading(false);
  }, []);

  const fetchUsers = useCallback(async () => {
    setUsersLoading(true);
    try {
      const data = await apiRequest<AdminUser[]>("/api/admin/users");
      setUsers(data);
    } catch { /* ignore */ }
    setUsersLoading(false);
  }, []);

  useEffect(() => {
    if (user?.is_admin) {
      fetchUsers();
    }
  }, [user, fetchUsers]);

  async function handleLogin(e: FormEvent) {
    e.preventDefault();
    setLoginError("");
    setLoginLoading(true);
    try {
      const data = await login(username, password);
      setUser(data.user);
    } catch (err) {
      setLoginError(err instanceof Error ? err.message : "登录失败");
    }
    setLoginLoading(false);
  }

  function handleSelectUser(u: AdminUser) {
    if (selectedUser?.id === u.id) {
      setSelectedUser(null);
      setUserRooms([]);
      setUserChars([]);
      setLoadingDetail(null);
      setActiveTab("rooms");
      return;
    }
    setSelectedUser(u);
    setUserRooms([]);
    setUserChars([]);
    setLoadingDetail(null);
    setActiveTab("rooms");
  }

  async function fetchRooms() {
    if (!selectedUser) return;
    setLoadingDetail("rooms");
    setActiveTab("rooms");
    setActionError("");
    try {
      const data = await apiRequest<UserRoom[]>(`/api/admin/users/${selectedUser.id}/rooms`);
      setUserRooms(data);
    } catch { setUserRooms([]); }
    setLoadingDetail(null);
  }

  async function fetchChars() {
    if (!selectedUser) return;
    setLoadingDetail("chars");
    setActiveTab("chars");
    try {
      const data = await apiRequest<UserChar[]>(`/api/admin/users/${selectedUser.id}/characters`);
      setUserChars(data);
    } catch { setUserChars([]); }
    setLoadingDetail(null);
  }

  useEffect(() => {
    if (selectedUser) {
      fetchRooms();
    }
  }, [selectedUser]);

  function removeRoomFromState(roomId: string) {
    if (!selectedUser) return;
    setUserRooms((prev) => prev.filter((r) => r.room_id !== roomId));
    setUsers((prev) =>
      prev.map((u) =>
        u.id === selectedUser.id ? { ...u, room_count: Math.max(0, u.room_count - 1) } : u
      )
    );
  }

  function handleDeleteRoom(roomId: string, roomName: string) {
    setDeleteConfirm({ roomId, roomName });
  }

  async function confirmDeleteRoom() {
    if (!deleteConfirm || !selectedUser) return;
    const roomId = deleteConfirm.roomId;
    setDeleteConfirm(null);
    setActionError("");
    setDeletingRoomId(roomId);
    try {
      await apiRequest(`/api/admin/rooms/${roomId}/delete`, { method: "POST" });
      removeRoomFromState(roomId);
    } catch {
      setActionError("删除房间失败，请检查权限或稍后重试");
    }
    setDeletingRoomId(null);
  }

  async function handleViewChar(charId: string) {
    if (!selectedUser) return;
    setCharDetailLoading(true);
    try {
      const data = await apiRequest<CharacterCard>(`/api/admin/users/${selectedUser.id}/characters/${charId}`);
      setCharDetail(data);
    } catch { /* ignore */ }
    setCharDetailLoading(false);
  }

  function renderCharDetail() {
    if (charDetailLoading) {
      return (
        <div style={{ padding: "24px", textAlign: "center", fontSize: "13px", color: "var(--text-muted)" }}>
          加载中...
        </div>
      );
    }
    if (!charDetail) return null;
    return <CharacterDetailModal character={charDetail} showWeapons onClose={() => setCharDetail(null)} />;
  }

  if (loading) {
    return (
      <div style={{ maxWidth: "600px", margin: "80px auto", padding: "0 24px", textAlign: "center", color: "var(--text-muted)", fontSize: "14px" }}>
        加载中...
      </div>
    );
  }

  if (!user) {
    return (
      <div style={{ maxWidth: "400px", margin: "80px auto", padding: "0 24px" }}>
        <form className="setup-card" onSubmit={handleLogin}>
          <p className="panel__kicker">CoC Yes Admin</p>
          <h2>管理员登录</h2>
          <p className="setup-card__desc">使用管理员账号登录以管理系统</p>
          <div className="setup-card__fields">
            <label>用户名
              <input type="text" value={username} onChange={(e) => setUsername(e.target.value)}
                required minLength={2} maxLength={32} autoComplete="username" autoFocus />
            </label>
            <label>密码
              <input type="password" value={password} onChange={(e) => setPassword(e.target.value)}
                required minLength={4} maxLength={128} autoComplete="current-password" />
            </label>
          </div>
          {loginError && (
            <p style={{ color: "var(--danger)", fontSize: "13px", margin: "12px 0 0 0", textAlign: "center" }}>{loginError}</p>
          )}
          <div className="setup-card__actions">
            <button className="button button--primary" type="submit" disabled={loginLoading}>
              {loginLoading ? "登录中..." : "登录"}
            </button>
          </div>
        </form>
      </div>
    );
  }

  if (!user.is_admin) {
    return (
      <div style={{ maxWidth: "400px", margin: "80px auto", padding: "0 24px" }}>
        <div className="setup-card" style={{ textAlign: "center" }}>
          <h2>访问被拒绝</h2>
          <p style={{ color: "var(--text-muted)", fontSize: "14px", margin: "12px 0 20px" }}>
            当前账号没有管理员权限。
          </p>
          <button className="button button--ghost button--sm" onClick={() => { clearAuth(); setUser(null); }}>
            切换账号
          </button>
        </div>
      </div>
    );
  }

  return (
    <div style={{ maxWidth: "1080px", margin: "40px auto", padding: "0 24px" }}>
      {charDetail && renderCharDetail()}

      {deleteConfirm && (
        <div className="modal-overlay" onClick={() => setDeleteConfirm(null)}>
          <div className="modal-panel" onClick={(e) => e.stopPropagation()} style={{ maxWidth: "360px", padding: "24px", textAlign: "center" }}>
            <h3 style={{ margin: "0 0 12px", fontSize: "16px" }}>确认删除房间</h3>
            <p style={{ margin: "0 0 8px", fontSize: "13px", color: "var(--text-muted)" }}>
              将永久删除房间
            </p>
            <p style={{ margin: "0 0 20px", fontSize: "14px", fontWeight: 600, color: "var(--text)" }}>
              {deleteConfirm.roomName}
            </p>
            <p style={{ margin: "0 0 20px", fontSize: "12px", color: "var(--danger)" }}>
              此操作不可撤销，将同时删除房间内的所有消息、角色卡和骰子记录。
            </p>
            <div style={{ display: "flex", gap: "8px", justifyContent: "center" }}>
              <button className="button button--danger" onClick={confirmDeleteRoom} type="button">
                确认删除
              </button>
              <button className="button button--ghost" onClick={() => setDeleteConfirm(null)} type="button">
                取消
              </button>
            </div>
          </div>
        </div>
      )}

      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "24px" }}>
        <div>
          <h2 style={{ margin: 0, fontSize: "20px" }}>用户管理</h2>
          <p style={{ margin: "4px 0 0", fontSize: "13px", color: "var(--text-muted)" }}>
            {user.display_name || user.username} — 管理员
          </p>
        </div>
        <button className="button button--ghost button--sm" onClick={() => { clearAuth(); setUser(null); }}>
          退出
        </button>
      </div>

      <div style={{ display: "flex", gap: "24px" }}>
        <div style={{ flex: users.length > 0 ? "0 0 340px" : "1", minWidth: 0 }}>
          <div className="setup-card" style={{ padding: "0" }}>
            <div style={{ padding: "16px", borderBottom: "1px solid var(--border)", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <span style={{ fontSize: "13px", color: "var(--text-muted)", fontWeight: 500 }}>
                所有用户 ({users.length})
              </span>
              <button className="button button--ghost button--sm" onClick={fetchUsers} type="button" title="刷新">
                {usersLoading ? "..." : "↻"}
              </button>
            </div>
            {users.length === 0 && !usersLoading && (
              <div style={{ padding: "24px", textAlign: "center", fontSize: "13px", color: "var(--text-muted)" }}>
                暂无用户
              </div>
            )}
            {usersLoading && users.length === 0 && (
              <div style={{ padding: "24px", textAlign: "center", fontSize: "13px", color: "var(--text-muted)" }}>
                加载中...
              </div>
            )}
            {users.length > 0 && (
              <div style={{ maxHeight: "500px", overflowY: "auto" }}>
                {users.map((u) => (
                  <button
                    key={u.id}
                    className="button--reset"
                    onClick={() => handleSelectUser(u)}
                    style={{
                      display: "flex", justifyContent: "space-between", alignItems: "center",
                      width: "100%", padding: "10px 16px", textAlign: "left",
                      borderBottom: "1px solid var(--border)",
                      background: selectedUser?.id === u.id ? "var(--bg-active)" : "transparent",
                      transition: "background 0.1s",
                    }}
                  >
                    <div style={{ minWidth: 0 }}>
                      <div style={{ fontSize: "13px", fontWeight: 500, color: "var(--text)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                        {u.display_name || u.username}
                        {u.is_admin ? (
                          <span style={{ fontSize: "10px", color: "var(--brand)", marginLeft: "6px", fontWeight: 400 }}>ADMIN</span>
                        ) : null}
                      </div>
                      <div style={{ fontSize: "11px", color: "var(--text-muted)", marginTop: "2px" }}>
                        @{u.username}
                      </div>
                    </div>
                    <div style={{ display: "flex", gap: "12px", flexShrink: 0, marginLeft: "12px", fontSize: "12px", color: "var(--text-secondary)" }}>
                      <span>{u.room_count} 房间</span>
                      <span>{u.character_count} 角色卡</span>
                    </div>
                  </button>
                ))}
              </div>
            )}
          </div>
        </div>

        <div style={{ flex: 1, minWidth: 0 }}>
          {!selectedUser ? (
            <div className="setup-card" style={{ textAlign: "center", padding: "48px 24px" }}>
              <p style={{ color: "var(--text-muted)", fontSize: "14px", margin: 0 }}>
                选择一个用户以查看 KP 数据和调查员数据
              </p>
            </div>
          ) : (
            <div className="setup-card" style={{ padding: "0" }}>
              <div style={{ padding: "16px", borderBottom: "1px solid var(--border)" }}>
                <div style={{ fontSize: "15px", fontWeight: 600, color: "var(--text)" }}>
                  {selectedUser.display_name || selectedUser.username}
                </div>
                <div style={{ fontSize: "12px", color: "var(--text-muted)", marginTop: "4px" }}>
                  @{selectedUser.username} · {selectedUser.room_count} 房间 · {selectedUser.character_count} 角色卡 · 创建于 {selectedUser.created_at.slice(0, 10)}
                </div>
              </div>

              <div style={{ display: "flex", borderBottom: "1px solid var(--border)" }}>
                <button
                  className="button--reset"
                  onClick={fetchRooms}
                  style={{
                    flex: 1, padding: "10px", textAlign: "center", fontSize: "13px",
                    color: activeTab === "rooms" ? "var(--text)" : "var(--text-muted)",
                    borderBottom: activeTab === "rooms" ? "2px solid var(--accent)" : "2px solid transparent",
                    fontWeight: activeTab === "rooms" ? 600 : 400,
                  }}
                >
                  KP ({selectedUser.room_count})
                </button>
                <button
                  className="button--reset"
                  onClick={fetchChars}
                  style={{
                    flex: 1, padding: "10px", textAlign: "center", fontSize: "13px",
                    color: activeTab === "chars" ? "var(--text)" : "var(--text-muted)",
                    borderBottom: activeTab === "chars" ? "2px solid var(--accent)" : "2px solid transparent",
                    fontWeight: activeTab === "chars" ? 600 : 400,
                  }}
                >
                  调查员 ({selectedUser.character_count})
                </button>
              </div>

              {loadingDetail && (
                <div style={{ padding: "24px", textAlign: "center", fontSize: "13px", color: "var(--text-muted)" }}>
                  加载中...
                </div>
              )}

              {actionError && (
                <div style={{ padding: "8px 16px", fontSize: "12px", color: "var(--danger)", textAlign: "center" }}>
                  {actionError}
                </div>
              )}

              {!loadingDetail && activeTab === "rooms" && (
                <>
                  {userRooms.length === 0 ? (
                    <div style={{ padding: "24px", textAlign: "center", fontSize: "13px", color: "var(--text-muted)" }}>
                      暂无房间记录
                    </div>
                  ) : (
                    <div style={{ maxHeight: "400px", overflowY: "auto" }}>
                      {userRooms.map((r) => (
                        <div
                          key={r.room_id}
                          style={{
                            display: "flex", justifyContent: "space-between", alignItems: "center",
                            padding: "10px 16px", borderBottom: "1px solid var(--border)",
                          }}
                        >
                          <div style={{ minWidth: 0, flex: 1 }}>
                            <div style={{ fontSize: "13px", fontWeight: 500, color: "var(--text)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                              {r.room_name}
                            </div>
                            <div style={{ display: "flex", gap: "8px", marginTop: "4px", alignItems: "center" }}>
                              <span style={{
                                fontSize: "10px", padding: "1px 6px", borderRadius: "3px",
                                background: r.status === "active" ? "rgba(106,170,106,0.15)" : r.status === "preparing" ? "rgba(200,155,70,0.15)" : "rgba(128,128,128,0.15)",
                                color: r.status === "active" ? "var(--success)" : r.status === "preparing" ? "var(--warning)" : "var(--text-muted)",
                              }}>
                                {ROOM_STATUS_LABELS[r.status] || r.status}
                              </span>
                              <span style={{
                                fontSize: "10px", padding: "1px 6px", borderRadius: "3px",
                                background: r.role === "keeper" ? "rgba(122,170,122,0.12)" : "rgba(128,128,128,0.10)",
                                color: r.role === "keeper" ? "var(--brand)" : "var(--text-muted)",
                              }}>
                                {ROLE_LABELS[r.role] || r.role}
                              </span>
                              <span style={{ fontSize: "10px", color: "var(--text-muted)" }}>
                                {r.joined_at.slice(0, 10)}
                              </span>
                            </div>
                          </div>
                          <button
                            className="button button--ghost button--sm"
                            onClick={() => handleDeleteRoom(r.room_id, r.room_name)}
                            disabled={deletingRoomId === r.room_id}
                            type="button"
                            style={{ flexShrink: 0, marginLeft: "12px", color: "var(--danger)" }}
                          >
                            {deletingRoomId === r.room_id ? "..." : "删除"}
                          </button>
                        </div>
                      ))}
                    </div>
                  )}
                </>
              )}

              {!loadingDetail && activeTab === "chars" && (
                <>
                  {userChars.length === 0 ? (
                    <div style={{ padding: "24px", textAlign: "center", fontSize: "13px", color: "var(--text-muted)" }}>
                      暂无角色卡数据
                    </div>
                  ) : (
                    <div style={{ maxHeight: "400px", overflowY: "auto" }}>
                      {userChars.map((c) => (
                        <div
                          key={c.id}
                          style={{
                            display: "flex", justifyContent: "space-between", alignItems: "center",
                            padding: "10px 16px", borderBottom: "1px solid var(--border)",
                          }}
                        >
                          <div style={{ minWidth: 0, flex: 1 }}>
                            <div style={{ fontSize: "13px", fontWeight: 500, color: "var(--text)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                              {c.name}
                            </div>
                            <div style={{ fontSize: "11px", color: "var(--text-muted)", marginTop: "2px" }}>
                              {c.source_filename} · 更新于 {c.updated_at.slice(0, 10)}
                            </div>
                          </div>
                          <button
                            className="button button--ghost button--sm"
                            onClick={() => handleViewChar(c.id)}
                            type="button"
                            style={{ flexShrink: 0, marginLeft: "12px" }}
                          >
                            查看
                          </button>
                        </div>
                      ))}
                    </div>
                  )}
                </>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
