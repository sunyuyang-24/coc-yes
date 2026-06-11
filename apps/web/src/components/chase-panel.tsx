"use client";

import { useState } from "react";
import type { ChaseState, CharacterCard } from "@coc-yes/shared";
import { apiUrl } from "@/lib/api";

type Props = {
  roomId: string;
  memberId: string;
  chase: ChaseState;
  characters: CharacterCard[];
  isKeeper: boolean;
  onClose: () => void;
};

export function ChasePanel({ roomId, memberId, chase, characters, isKeeper, onClose }: Props) {
  const [participantId, setParticipantId] = useState("");
  const [actionType, setActionType] = useState<"speed_check" | "maneuver" | "conflict">("speed_check");
  const [weaponIndex, setWeaponIndex] = useState<number | undefined>(undefined);
  const [hidden, setHidden] = useState(false);
  const [sending, setSending] = useState(false);

  async function act() {
    if (sending || !participantId) return;
    setSending(true);
    try {
      const res = await fetch(apiUrl(`/api/rooms/${roomId}/chase/action`), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          participantId,
          actionType,
          weaponIndex: actionType === "conflict" ? (weaponIndex ?? 0) : null,
          hidden: hidden && isKeeper,
        }),
      });
      if (!res.ok) {
        const err = await res.text();
        console.error("Chase action failed:", err);
      }
    } finally {
      setSending(false);
    }
  }

  async function endChase() {
    const form = new FormData();
    form.append("editorId", memberId);
    const res = await fetch(apiUrl(`/api/rooms/${roomId}/chase/end`), { method: "POST", body: form });
    if (res.ok) onClose();
  }

  const maxPos = Math.max(...chase.participants.map((p) => p.position), 10);

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-panel" onClick={(e) => e.stopPropagation()} style={{ maxWidth: "560px" }}>
        <div className="modal-panel__header">
          <span className="modal-panel__title">🏃 追逐</span>
          <button className="button button--ghost button--sm" onClick={onClose} type="button">✕</button>
        </div>

        <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
          {/* Position Track */}
          <div className="chase__track">
            {Array.from({ length: maxPos + 1 }, (_, pos) => {
              const atPos = chase.participants.filter((p) => p.position === pos);
              const obstacle = chase.obstacles.find((o) => o.position === pos);
              return (
                <div key={pos} className="chase__track-cell">
                  <span className="chase__track-num">{pos}</span>
                  {obstacle && (
                    <div className={`chase__obstacle ${obstacle.resolved ? "chase__obstacle--resolved" : ""}`}
                      title={obstacle.label}>
                      {obstacle.type === "hazard" ? "⚠" : "🚧"}
                    </div>
                  )}
                  {atPos.map((p) => {
                    const char = characters.find((c) => c.id === p.characterId);
                    return (
                      <div key={p.characterId}
                        className={`chase__participant chase__participant--${p.role}`}
                        title={`${char?.basic?.name || p.displayName} MOV ${p.mov}`}>
                        {char?.basic?.name?.charAt(0) || p.displayName.charAt(0)}
                      </div>
                    );
                  })}
                </div>
              );
            })}
          </div>

          {/* Participant List */}
          <div className="chase__list">
            {chase.participants.map((p) => {
              const char = characters.find((c) => c.id === p.characterId);
              return (
                <div key={p.characterId} className="chase__list-item">
                  <span className={`chase__role-badge chase__role-badge--${p.role}`}>
                    {p.role === "pursuer" ? "追" : "逃"}
                  </span>
                  <span>{char?.basic?.name || p.displayName}</span>
                  <span style={{ color: "var(--text-muted)", fontSize: "12px" }}>MOV {p.mov}</span>
                  <span style={{ color: "var(--text-secondary)", fontSize: "12px" }}>位置 {p.position}</span>
                </div>
              );
            })}
          </div>

          {/* Obstacles */}
          {chase.obstacles.length > 0 && (
            <div className="chase__obstacles">
              {chase.obstacles.map((o, i) => (
                <div key={i} className={`chase__obstacle-item ${o.resolved ? "chase__obstacle-item--resolved" : ""}`}>
                  <span>{o.type === "hazard" ? "⚠" : "🚧"}</span>
                  <span>位置 {o.position}: {o.label}</span>
                  {o.resolved && <span style={{ color: "var(--success)", fontSize: "11px" }}>已解决</span>}
                </div>
              ))}
            </div>
          )}

          {/* Action Form (KP only) */}
          {isKeeper && (
            <div style={{ display: "flex", flexDirection: "column", gap: "10px", padding: "12px", background: "var(--bg-hover)", borderRadius: "var(--radius)" }}>
              <div className="combat__field">
                <label>行动者</label>
                <select value={participantId} onChange={(e) => setParticipantId(e.target.value)}>
                  <option value="">选择...</option>
                  {chase.participants.map((p) => {
                    const c = characters.find((ch) => ch.id === p.characterId);
                    return (
                      <option key={p.memberId} value={p.memberId}>
                        {c?.basic?.name || p.displayName} ({p.role === "pursuer" ? "追" : "逃"})
                      </option>
                    );
                  })}
                </select>
              </div>

              <div className="combat__field">
                <label>行动类型</label>
                <select value={actionType} onChange={(e) => setActionType(e.target.value as typeof actionType)}>
                  <option value="speed_check">速度检定 (CON)</option>
                  <option value="maneuver">移动 (MANEUVER)</option>
                  <option value="conflict">冲突 (CONFLICT)</option>
                </select>
              </div>

              {actionType === "conflict" && (
                <div className="combat__field">
                  <label>武器序号</label>
                  <input type="number" min={0} value={weaponIndex ?? 0}
                    onChange={(e) => setWeaponIndex(Number(e.target.value))} />
                </div>
              )}

              <label style={{ fontSize: "12px", display: "flex", alignItems: "center", gap: "6px" }}>
                <input type="checkbox" checked={hidden} onChange={(e) => setHidden(e.target.checked)} />
                暗投
              </label>

              <div style={{ display: "flex", gap: "8px" }}>
                <button className="button button--primary button--sm" onClick={act} disabled={sending || !participantId} type="button">
                  {sending ? "执行中..." : "执行行动"}
                </button>
                <button className="button button--ghost button--sm" onClick={endChase} type="button">结束追逐</button>
              </div>
            </div>
          )}

          {!isKeeper && (
            <p style={{ textAlign: "center", color: "var(--text-muted)", padding: "16px", fontSize: "13px" }}>
              等待 KP 操作...
            </p>
          )}
        </div>
      </div>
    </div>
  );
}
