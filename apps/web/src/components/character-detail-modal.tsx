"use client";

import type { CharacterCard } from "@coc-yes/shared";
import { ATTRIBUTE_LABELS, STATUS_LABELS } from "@coc-yes/shared";

export function CharacterDetailModal({
  character,
  showWeapons = false,
  maxSkills = 50,
  onClose,
}: {
  character: CharacterCard;
  showWeapons?: boolean;
  maxSkills?: number;
  onClose: () => void;
}) {
  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-panel" onClick={(e) => e.stopPropagation()} style={{
        maxWidth: "700px", maxHeight: "80vh", overflowY: "auto", padding: "24px",
      }}>
        <h3 style={{ marginTop: 0 }}>{character.basic?.name || character.sourceFileName}</h3>
        <p style={{ fontSize: "13px", color: "var(--text-muted)", marginTop: 0 }}>
          {character.basic?.occupation || "未读取职业"} · {character.basic?.age || "年龄未知"}
        </p>

        <div className="char-card__attrs">
          {character.attributes?.map((a) => (
            <div key={a.key} className="char-card__attr">
              <span className="char-card__attr-key">{ATTRIBUTE_LABELS[a.key] || a.key}</span>
              <span className="char-card__attr-val">{a.value ?? "?"}</span>
            </div>
          ))}
        </div>

        <div className="char-card__section">
          <h4>状态</h4>
          <div style={{ display: "flex", flexWrap: "wrap", gap: "8px" }}>
            {Object.entries(character.status || {}).map(([k, v]) => {
              if (v == null) return null;
              const label = STATUS_LABELS[k];
              if (!label) return null;
              const init = character.initialStatus?.[k];
              return (
                <span key={k} style={{
                  padding: "4px 10px", background: "var(--bg-hover)", borderRadius: "var(--radius-sm)",
                  fontSize: "13px",
                }}>
                  <span style={{ color: "var(--text-muted)" }}>{label}: </span>
                  <span style={{ fontWeight: 600, color: "var(--text)" }}>
                    {init != null ? `${init}/` : ""}{v}
                  </span>
                </span>
              );
            })}
            {character.status?.luck == null && (() => {
              const luckVal = character.attributes?.find((a) => a.key === "LUCK")?.value;
              if (luckVal == null) return null;
              return (
                <span style={{ padding: "4px 10px", background: "var(--bg-hover)", borderRadius: "var(--radius-sm)", fontSize: "13px" }}>
                  <span style={{ color: "var(--text-muted)" }}>幸运: </span>
                  <span style={{ fontWeight: 600, color: "#FFD54F" }}>{luckVal}</span>
                </span>
              );
            })()}
          </div>
        </div>

        {character.skills?.length > 0 && (
          <div className="char-card__section">
            <h4>技能</h4>
            <div className="char-card__skills">
              {character.skills.filter((s) => s.value != null).slice(0, maxSkills).map((s) => (
                <div key={s.name} className="char-card__skill">
                  <span className="char-card__skill-name">{s.name}</span>
                  <span className="char-card__skill-val">{s.value}</span>
                </div>
              ))}
            </div>
          </div>
        )}

        {showWeapons && character.weapons?.length > 0 && (
          <div className="char-card__section">
            <h4>武器</h4>
            {character.weapons.map((w, i) => (
              <div key={i} style={{ fontSize: "13px", marginBottom: "4px" }}>
                <span style={{ fontWeight: 500 }}>{w.name || "武器"}</span>
                {" · "}{String(w.damage || "?")}
              </div>
            ))}
          </div>
        )}

        <button className="button button--ghost button--sm" onClick={onClose} style={{ marginTop: "12px", width: "100%" }}>
          关闭
        </button>
      </div>
    </div>
  );
}
