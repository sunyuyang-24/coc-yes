"use client";

import { useState } from "react";
import type { CombatState, CharacterCard } from "@coc-yes/shared";
import { apiUrl } from "@/lib/api";

type Props = {
  roomId: string;
  memberId: string;
  combat: CombatState;
  characters: CharacterCard[];
  isKeeper: boolean;
  onClose: () => void;
};

export function CombatPanel({ roomId, memberId, combat, characters, isKeeper, onClose }: Props) {
  const [attackerId, setAttackerId] = useState(combat.actors[combat.currentActorIndex]?.memberId || "");
  const [defenderId, setDefenderId] = useState("");
  const [actionType, setActionType] = useState<"attack" | "dodge" | "maneuver" | "fight_back">("attack");
  const [weaponIndex, setWeaponIndex] = useState(0);
  const [hidden, setHidden] = useState(false);
  const [sending, setSending] = useState(false);

  const currentActor = combat.actors[combat.currentActorIndex];

  async function act() {
    if (sending || !attackerId || !defenderId) return;
    setSending(true);
    try {
      const res = await fetch(apiUrl(`/api/rooms/${roomId}/combat/action`), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          attackerId,
          weaponIndex,
          defenderId,
          actionType,
          hidden: hidden && isKeeper,
        }),
      });
      if (!res.ok) {
        const err = await res.text();
        console.error("Combat action failed:", err);
      }
    } finally {
      setSending(false);
    }
  }

  async function endCombat() {
    const form = new FormData();
    form.append("editorId", memberId);
    const res = await fetch(apiUrl(`/api/rooms/${roomId}/combat/end`), { method: "POST", body: form });
    if (res.ok) onClose();
  }

  const currentChar = characters.find((c) => c.id === currentActor?.characterId);
  const weapons = currentChar?.weapons || [];

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-panel" onClick={(e) => e.stopPropagation()} style={{ maxWidth: "560px" }}>
        <div className="modal-panel__header">
          <span className="modal-panel__title">⚔️ 战斗 — 第 {combat.roundNumber} 轮</span>
          <button className="button button--ghost button--sm" onClick={onClose} type="button">✕</button>
        </div>

        <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
          {/* Initiative Order */}
          <div className="combat__initiative">
            {combat.actors.map((actor, i) => {
              const isCurrent = i === combat.currentActorIndex;
              const char = characters.find((c) => c.id === actor.characterId);
              return (
                <div key={actor.characterId}
                  className={`combat__actor ${isCurrent ? "combat__actor--current" : ""} ${actor.hasActedThisRound ? "combat__actor--acted" : ""}`}>
                  <span className="combat__actor-dex">DEX {actor.dex}</span>
                  <span className="combat__actor-name">{char?.basic?.name || actor.displayName}</span>
                  <span className="combat__actor-hp">HP {actor.hp}/{actor.hpMax}</span>
                  {actor.db !== "0" && <span className="combat__actor-db">{actor.db}</span>}
                  {isCurrent && <span className="combat__actor-arrow">◀</span>}
                </div>
              );
            })}
          </div>

          {/* Action Form */}
          {isKeeper && currentActor && (
            <div style={{ display: "flex", flexDirection: "column", gap: "10px", padding: "12px", background: "var(--bg-hover)", borderRadius: "var(--radius)" }}>
              <div style={{ fontSize: "13px", color: "var(--brand)" }}>
                当前行动: {currentChar?.basic?.name || currentActor.displayName}
              </div>

              <div className="combat__field">
                <label>行动类型</label>
                <select value={actionType} onChange={(e) => setActionType(e.target.value as typeof actionType)}>
                  <option value="attack">攻击</option>
                  <option value="dodge">闪避</option>
                  <option value="maneuver">战技</option>
                  <option value="fight_back">反击</option>
                </select>
              </div>

              {(actionType === "attack" || actionType === "fight_back") && weapons.length > 0 && (
                <div className="combat__field">
                  <label>武器</label>
                  <select value={weaponIndex} onChange={(e) => setWeaponIndex(Number(e.target.value))}>
                    {weapons.map((w, i) => (
                      <option key={i} value={i}>{w.name || `武器 ${i + 1}`} — {w.damage || "?"}</option>
                    ))}
                  </select>
                </div>
              )}

              <div className="combat__field">
                <label>目标</label>
                <select value={defenderId} onChange={(e) => setDefenderId(e.target.value)}>
                  <option value="">选择目标...</option>
                  {combat.actors.filter((a) => a.memberId !== currentActor.memberId).map((a) => {
                    const c = characters.find((ch) => ch.id === a.characterId);
                    return (
                      <option key={a.memberId} value={a.memberId}>
                        {c?.basic?.name || a.displayName} (HP {a.hp}/{a.hpMax})
                      </option>
                    );
                  })}
                </select>
              </div>

              <label style={{ fontSize: "12px", display: "flex", alignItems: "center", gap: "6px" }}>
                <input type="checkbox" checked={hidden} onChange={(e) => setHidden(e.target.checked)} />
                暗投
              </label>

              <div style={{ display: "flex", gap: "8px" }}>
                <button className="button button--primary button--sm" onClick={act} disabled={sending || !defenderId} type="button">
                  {sending ? "执行中..." : "执行行动"}
                </button>
                <button className="button button--ghost button--sm" onClick={endCombat} type="button">结束战斗</button>
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
