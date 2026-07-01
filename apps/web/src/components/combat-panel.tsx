"use client";

import { useEffect, useMemo, useState } from "react";
import type {
  CombatState,
  CombatParticipant,
  CharacterCard,
} from "@coc-yes/shared";
import { apiRequest } from "@/lib/api";

type Props = {
  roomId: string;
  memberId: string;
  combat: CombatState;
  characters: CharacterCard[];
  isKeeper: boolean;
  onClose: () => void;
};

type DeclarationDraft = {
  characterId: string;
  actionType: "melee_attack" | "melee_maneuver" | "skip";
  weaponIndex: number | null;
  targetCharacterId: string | null;
};

type DefenseDraft = {
  intentId: string;
  defenderCharacterId: string;
  defenseType: "dodge" | "fight_back" | "maneuver" | "none";
  weaponIndex: number | null;
};

const STATUS_LABEL: Record<CombatParticipant["status"], string> = {
  active: "正常",
  unconscious: "昏迷",
  dying: "濒死",
  dead: "死亡",
};

type Weapon = { name?: string; damage?: string };

function getWeapons(char: CharacterCard | undefined): Weapon[] {
  return (char?.weapons as Weapon[] | undefined) || [];
}

function getCharDisplayName(char: CharacterCard | undefined, participant: CombatParticipant): string {
  return char?.basic?.name || participant.displayName;
}

function isInvalidCombatant(p: CombatParticipant): boolean {
  return p.status === "unconscious" || p.status === "dying" || p.status === "dead";
}

export function CombatPanel({
  roomId, memberId, combat, characters, isKeeper, onClose,
}: Props) {
  const [busy, setBusy] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const charMap = useMemo(
    () => new Map(characters.map(c => [c.id, c])),
    [characters],
  );

  const participantMap = useMemo(
    () => new Map(combat.participants.map(p => [p.characterId, p])),
    [combat.participants],
  );

  const [drafts, setDrafts] = useState<Record<string, DeclarationDraft>>(() => {
    const init: Record<string, DeclarationDraft> = {};
    for (const p of combat.participants) {
      const weapons = getWeapons(charMap.get(p.characterId));
      init[p.characterId] = {
        characterId: p.characterId,
        actionType: "melee_attack",
        weaponIndex: weapons.length > 0 ? 0 : null,
        targetCharacterId: null,
      };
    }
    return init;
  });

  const [defenses, setDefenses] = useState<Record<string, DefenseDraft>>({});

  useEffect(() => {
    if (combat.phase === "declaration") setDefenses({});
  }, [combat.phase, combat.roundNumber]);

  const intents = combat.intents || [];
  const participants = combat.participants || [];
  const logs = combat.logs || [];

  function canEditFor(p: CombatParticipant): boolean {
    return isKeeper || p.controllerMemberId === memberId;
  }

  // --- State helpers ---

  function patchDraft(characterId: string, patch: Partial<DeclarationDraft>) {
    setDrafts(prev => ({
      ...prev,
      [characterId]: { ...prev[characterId], ...patch },
    }));
  }

  function patchDefense(key: string, patch: Partial<DefenseDraft>) {
    setDefenses(prev => {
      const base = prev[key] ?? {
        intentId: "",
        defenderCharacterId: "",
        defenseType: "none" as const,
        weaponIndex: null,
      };
      return {
        ...prev,
        [key]: { ...base, ...patch },
      };
    });
  }

  // --- Actions ---

  async function submitDeclarations() {
    if (busy) return;
    setErrorMsg(null);
    setBusy(true);
    try {
      const body: Array<{
        characterId: string;
        actionType: "melee_attack" | "melee_maneuver" | "skip";
        weaponIndex?: number;
        targetCharacterIds: string[];
      }> = [];
      let downgradedToSkip = 0;
      for (const p of participants) {
        if (isInvalidCombatant(p)) continue;
        if (!canEditFor(p)) continue;
        const d = drafts[p.characterId];
        if (!d) continue;
        // 未选目标的攻击/战技 → 转换为 skip，避免"一名 NPC 未配置目标就
        // 导致整批声明失败"的情况；同时保留有目标配置的 NPC 声明。
        if (d.actionType !== "skip" && !d.targetCharacterId) {
          body.push({
            characterId: p.characterId,
            actionType: "skip",
            targetCharacterIds: [],
          });
          downgradedToSkip += 1;
          continue;
        }
        body.push({
          characterId: p.characterId,
          actionType: d.actionType,
          weaponIndex: d.weaponIndex ?? undefined,
          targetCharacterIds: d.targetCharacterId ? [d.targetCharacterId] : [],
        });
      }
      if (body.length === 0) {
        setErrorMsg("尚未选择任何行动。请为可行动的角色声明行动。");
        return;
      }
      // 若提交内容全部都是 skip（包括被降级的），告诉用户至少声明一个
      // 实际行动；但仍然允许提交一个空 body 以外的混合集合。
      if (body.every((b) => b.actionType === "skip")) {
        setErrorMsg(
          downgradedToSkip > 0
            ? `有 ${downgradedToSkip} 个角色未选目标，已被自动转为跳过；请至少为一名角色声明真实行动（攻击/战技 + 目标）。`
            : "所有声明均为跳过。请至少声明一条非跳过行动。",
        );
        return;
      }
      await apiRequest(`/api/rooms/${roomId}/combat/declare`, {
        method: "POST",
        body: JSON.stringify({ memberId, declarations: body }),
      });
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err);
      setErrorMsg(`声明失败：${message}`);
    } finally {
      setBusy(false);
    }
  }

  async function submitLock() {
    if (busy || !isKeeper) return;
    setErrorMsg(null);
    setBusy(true);
    try {
      await apiRequest(`/api/rooms/${roomId}/combat/lock`, {
        method: "POST",
        body: JSON.stringify({ editorId: memberId }),
      });
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err);
      setErrorMsg(`锁定失败：${message}`);
    } finally {
      setBusy(false);
    }
  }

  async function submitDefenses() {
    if (busy) return;
    setErrorMsg(null);
    setBusy(true);
    try {
      const defArr = Object.values(defenses);
      if (defArr.length === 0) {
        setErrorMsg("尚未选择任何防守反应。");
        return;
      }
      await apiRequest(`/api/rooms/${roomId}/combat/defense`, {
        method: "POST",
        body: JSON.stringify({ memberId, defenses: defArr }),
      });
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err);
      setErrorMsg(`防守提交失败：${message}`);
    } finally {
      setBusy(false);
    }
  }

  async function submitResolve() {
    if (busy || !isKeeper) return;
    setErrorMsg(null);
    setBusy(true);
    try {
      await apiRequest(`/api/rooms/${roomId}/combat/resolve`, {
        method: "POST",
        body: JSON.stringify({ editorId: memberId }),
      });
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err);
      setErrorMsg(`结算失败：${message}`);
    } finally {
      setBusy(false);
    }
  }

  async function submitNextRound() {
    if (busy || !isKeeper) return;
    setErrorMsg(null);
    setBusy(true);
    try {
      await apiRequest(`/api/rooms/${roomId}/combat/next_round`, {
        method: "POST",
        body: JSON.stringify({ editorId: memberId }),
      });
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err);
      setErrorMsg(`进入下一轮失败：${message}`);
    } finally {
      setBusy(false);
    }
  }

  async function endCombat() {
    if (busy || !isKeeper) return;
    if (!confirm("确认结束这场战斗？")) return;
    setErrorMsg(null);
    setBusy(true);
    try {
      await apiRequest(`/api/rooms/${roomId}/combat/end`, {
        method: "POST",
        body: JSON.stringify({ editorId: memberId }),
      });
      onClose();
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err);
      setErrorMsg(`结束失败：${message}`);
    } finally {
      setBusy(false);
    }
  }

  // --- Derived data ---

  const targetOptionsByCharacterId = useMemo(() => {
    const map: Record<string, CombatParticipant[]> = {};
    for (const p of participants) {
      if (p.status === "dead") continue;
      map[p.characterId] = participants.filter(
        t => t.characterId !== p.characterId && t.status !== "dead",
      );
    }
    return map;
  }, [participants]);

  // 至少有一个声明不是“跳过”；仅用于禁用无意义按钮。
  const declarationHidesAction = useMemo(() => {
    const editable = participants.filter(
      (p) => !isInvalidCombatant(p) && canEditFor(p),
    );
    if (editable.length === 0) return true;
    return editable.every(
      (p) => drafts[p.characterId]?.actionType === "skip",
    );
  }, [drafts, participants]);

  // --- Render ---

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div
        className="modal-panel"
        onClick={(e) => e.stopPropagation()}
        style={{ maxWidth: "880px" }}
      >
        <div className="modal-panel__header">
          <span className="modal-panel__title">
            ⚔️ 战斗 — Round {combat.roundNumber}
            {combat.phase === "declaration" ? "（宣告阶段）" : "（结算阶段）"}
          </span>
          <button className="button button--ghost button--sm" onClick={onClose} type="button">
            ✕
          </button>
        </div>

        {errorMsg && (
          <div
            style={{
              marginTop: "12px",
              padding: "8px 10px",
              borderRadius: "6px",
              background: "var(--danger-bg, #fde8e8)",
              color: "var(--danger-fg, #c53030)",
              border: "1px solid var(--danger-border, #fc8181)",
              fontSize: "13px",
            }}
          >
            {errorMsg}
          </div>
        )}

        <div className="combat__participants">
          {participants.map((p) => {
            const char = charMap.get(p.characterId);
            return (
              <div
                key={p.characterId}
                className={`combat__actor ${isInvalidCombatant(p) ? "combat__actor--acted" : ""}`}
              >
                <div className="combat__actor-row">
                  <span className="combat__actor-dex">DEX {p.dex}</span>
                  <span className="combat__actor-name">
                    {getCharDisplayName(char, p)}
                    {char?.ownerId ? "" : " (NPC)"}
                  </span>
                  <span className="combat__actor-hp">
                    HP {p.hp}/{p.hpMax}
                  </span>
                  {p.armor > 0 && <span>护甲 {p.armor}</span>}
                  {p.db !== "0" && <span>DB {p.db}</span>}
                  <span>Build {p.build}</span>
                  <span className="combat__actor-status">
                    {STATUS_LABEL[p.status] || p.status}
                    {p.majorWound && (
                      <span style={{
                        marginLeft: "6px",
                        display: "inline-block",
                        padding: "1px 6px",
                        fontSize: "11px",
                        borderRadius: "999px",
                        background: "var(--danger-bg, #fde8e8)",
                        color: "var(--danger-fg, #c53030)",
                        border: "1px solid var(--danger-border, #fc8181)",
                      }}>重伤</span>
                    )}
                  </span>
                </div>
              </div>
            );
          })}
        </div>

        {combat.phase === "declaration" && (
          <div style={{ display: "flex", flexDirection: "column", gap: "12px", marginTop: "12px" }}>
            <div style={{ fontSize: "13px", color: "var(--text-muted)" }}>
              {isKeeper
                ? "KP：为每位参与者声明本轮意图（近战攻击/战技/跳过）。"
                : "在此声明你自己的本轮意图。"}
            </div>

            {participants.map((p) => {
              const disabled = isInvalidCombatant(p) || !canEditFor(p);
              const draft = drafts[p.characterId];
              const char = charMap.get(p.characterId);
              const weapons = getWeapons(char);
              if (!draft) return null;

              return (
                <div
                  key={p.characterId}
                  className="combat__field-block"
                  style={{ opacity: disabled ? 0.5 : 1 }}
                >
                  <div style={{ fontSize: "13px", fontWeight: 600 }}>
                    {getCharDisplayName(char, p)}
                    {!canEditFor(p) && !isKeeper ? " — 由对方玩家控制" : ""}
                  </div>

                  <div className="combat__field">
                    <label>行动类型</label>
                    <select
                      value={draft.actionType}
                      onChange={(e) =>
                        patchDraft(p.characterId, { actionType: e.target.value as DeclarationDraft["actionType"] })
                      }
                      disabled={disabled}
                    >
                      <option value="melee_attack">近战攻击</option>
                      <option value="melee_maneuver">战技（位置控制）</option>
                      <option value="skip">跳过本轮</option>
                    </select>
                  </div>

                  {draft.actionType !== "skip" && weapons.length > 0 && (
                    <div className="combat__field">
                      <label>武器</label>
                      <select
                        value={draft.weaponIndex ?? 0}
                        onChange={(e) =>
                          patchDraft(p.characterId, { weaponIndex: Number(e.target.value) })
                        }
                        disabled={disabled}
                      >
                        {weapons.map((w, i) => (
                          <option key={i} value={i}>
                            {w.name || `武器 ${i + 1}`} — {w.damage || "?"}
                          </option>
                        ))}
                      </select>
                    </div>
                  )}
                  {draft.actionType !== "skip" && weapons.length === 0 && (
                    <div style={{ fontSize: "12px", color: "var(--text-muted)" }}>
                      (该角色卡尚未配置武器，默认徒手 1D3)
                    </div>
                  )}

                  {draft.actionType !== "skip" && (
                    <div className="combat__field">
                      <label>目标（近战每次一个）</label>
                      <select
                        value={draft.targetCharacterId ?? ""}
                        onChange={(e) =>
                          patchDraft(p.characterId, {
                            targetCharacterId: e.target.value || null,
                          })
                        }
                        disabled={disabled}
                      >
                        <option value="">— 请选择目标 —</option>
                        {(targetOptionsByCharacterId[p.characterId] || []).map(t => {
                          const tchar = charMap.get(t.characterId);
                          return (
                            <option key={t.characterId} value={t.characterId}>
                              {getCharDisplayName(tchar, t)} (HP {t.hp})
                            </option>
                          );
                        })}
                      </select>
                    </div>
                  )}
                </div>
              );
            })}

            <div style={{ display: "flex", gap: "8px", justifyContent: "flex-end", flexWrap: "wrap" }}>
              <button
                className="button button--primary button--sm"
                onClick={submitDeclarations}
                disabled={busy || declarationHidesAction}
                type="button"
              >
                {busy ? "提交中..." : "提交声明"}
              </button>
              {isKeeper && (
                <button
                  className="button button--ghost button--sm"
                  onClick={submitLock}
                  disabled={busy || declarationHidesAction}
                  type="button"
                  title="锁定本轮声明并进入防守/结算阶段"
                >
                  {busy ? "锁定中..." : "锁定声明（KP）"}
                </button>
              )}
            </div>
          </div>
        )}

        {combat.phase === "resolution" && (
          <div style={{ display: "flex", flexDirection: "column", gap: "12px", marginTop: "12px" }}>
            <div style={{ fontSize: "13px", color: "var(--text-muted)" }}>
              在此为每个攻击意图选择防守反应。
              {isKeeper ? "（KP：可代所有角色选择。最后点击“结算全部”）" : "（普通玩家：仅能为自己的角色选择）"}
            </div>

            {intents.length === 0 && (
              <div style={{ fontSize: "13px", color: "var(--text-muted)" }}>
                本轮尚未声明任何行动。
              </div>
            )}

            {intents.map((it) => {
              if (it.actionType === "skip") return null;
              const attacker = participantMap.get(it.attackerCharacterId);
              if (!attacker) return null;
              const attackerChar = charMap.get(it.attackerCharacterId);
              const targets = (it.targetCharacterIds || [])
                .map(id => participantMap.get(id))
                .filter(Boolean) as CombatParticipant[];

              return (
                <div key={it.intentId} className="combat__field-block">
                  <div style={{ fontSize: "13px", fontWeight: 600 }}>
                    🗡️ {getCharDisplayName(attackerChar, attacker)}{" "}
                    对 {targets.map(t => {
                      const tc = charMap.get(t.characterId);
                      return getCharDisplayName(tc, t);
                    }).join("、")}{" "}
                    — {it.actionType === "melee_attack" ? "近战攻击" : "战技"}
                    {it.resolved ? "（已结算）" : ""}
                  </div>

                  {!it.resolved && targets.map((t) => {
                    const defKey = `${it.intentId}__${t.characterId}`;
                    const def = defenses[defKey] || {
                      intentId: it.intentId,
                      defenderCharacterId: t.characterId,
                      defenseType: "none",
                      weaponIndex: null,
                    };
                    const ownControl = isKeeper || t.controllerMemberId === memberId;
                    const tchar = charMap.get(t.characterId);
                    const tweapons = getWeapons(tchar);

                    return (
                      <div key={t.characterId} className="combat__field">
                        <label>
                          {getCharDisplayName(tchar, t)} 的防守反应
                        </label>
                        <select
                          value={def.defenseType}
                          disabled={!ownControl}
                          onChange={(e) =>
                            patchDefense(defKey, {
                              intentId: it.intentId,
                              defenderCharacterId: t.characterId,
                              defenseType: e.target.value as DefenseDraft["defenseType"],
                            })
                          }
                        >
                          <option value="none">无反应（对方直接掷骰）</option>
                          <option value="dodge">闪避（闪避技能，默认 DEX/2，平局防守方胜）</option>
                          <option value="fight_back">反击（武器技能，平局攻击方胜）</option>
                          <option value="maneuver">战技（STR/DEX/SIZ 最高）</option>
                        </select>
                        {def.defenseType === "fight_back" && tweapons.length > 0 && (
                          <select
                            value={def.weaponIndex ?? 0}
                            disabled={!ownControl}
                            onChange={(e) =>
                            patchDefense(defKey, {
                              intentId: it.intentId,
                              defenderCharacterId: t.characterId,
                              weaponIndex: Number(e.target.value),
                            })
                          }
                            style={{ marginLeft: "8px" }}
                          >
                            {tweapons.map((w, i) => (
                              <option key={i} value={i}>
                                {w.name || `武器 ${i + 1}`} — {w.damage || "?"}
                              </option>
                            ))}
                          </select>
                        )}
                      </div>
                    );
                  })}
                </div>
              );
            })}

            <div style={{ display: "flex", gap: "8px", justifyContent: "flex-end", flexWrap: "wrap" }}>
              <button
                className="button button--primary button--sm"
                onClick={submitDefenses}
                disabled={busy}
                type="button"
              >
                {busy ? "提交中..." : "提交防守"}
              </button>
              <button
                className="button button--primary button--sm"
                onClick={submitResolve}
                disabled={busy || !isKeeper}
                type="button"
                title={!isKeeper ? "仅 KP 可结算" : ""}
              >
                {busy ? "结算中..." : "结算全部（KP）"}
              </button>
              <button
                className="button button--ghost button--sm"
                onClick={submitNextRound}
                disabled={busy || !isKeeper}
                type="button"
              >
                进入下一轮
              </button>
              {isKeeper && (
                <button
                  className="button button--ghost button--sm"
                  onClick={endCombat}
                  type="button"
                >
                  结束战斗
                </button>
              )}
            </div>
          </div>
        )}

        {logs.length > 0 && (
          <div style={{ marginTop: "16px", borderTop: "1px solid var(--border)", paddingTop: "12px" }}>
            <div style={{ fontSize: "13px", fontWeight: 600, marginBottom: "6px" }}>
              战斗日志（最新在顶）
            </div>
            <div style={{ display: "flex", flexDirection: "column", gap: "6px", maxHeight: "220px", overflowY: "auto" }}>
              {logs.slice(0, 30).map((log, idx) => (
                <div
                  key={idx}
                  className="combat__log"
                  style={{
                    background: "var(--bg-hover)",
                    padding: "8px 10px",
                    borderRadius: "6px",
                    fontSize: "13px",
                  }}
                >
                  <div style={{ fontWeight: 600 }}>
                    Round {log.roundNumber} — {log.attacker.displayName} vs {log.defender.displayName}
                  </div>
                  <div style={{ color: "var(--text-secondary)" }}>
                    [{log.defender.defenseType}] {log.resultText}
                  </div>
                  <div style={{ color: "var(--text-secondary)", fontSize: "12px" }}>
                    {log.attacker.roll ? (
                      <>攻击出目: {log.attacker.roll.total}/{log.attacker.roll.targetValue}
                        {log.attacker.roll.successLabel ? ` (${log.attacker.roll.successLabel})` : ""}
                      </>
                    ) : (
                      <>攻击出目: 未投掷</>
                    )}
                    {log.defender.roll && (
                      <>
                        {" · "} 防守出目: {log.defender.roll.total}/{log.defender.roll.targetValue}
                        {log.defender.roll.successLabel ? ` (${log.defender.roll.successLabel})` : ""}
                      </>
                    )}
                  </div>
                  {log.damageAfterArmor != null && (
                    <div style={{ fontSize: "12px", color: "var(--text-secondary)" }}>
                      基础伤害 {log.damageRolled} · 扣护甲 {log.armorUsed ?? 0} · 实际扣血 {log.damageAfterArmor}
                      {log.impale ? " · 穿刺!" : ""}
                      {log.majorWound ? " · 达到重伤阈值" : ""}
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
