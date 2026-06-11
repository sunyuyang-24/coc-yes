"use client";

import type { FormEvent } from "react";
import { useState } from "react";
import type { CharacterCard } from "@coc-yes/shared";

export function CharacterCardView({
  canEdit,
  canRoll,
  character,
  onRoll,
  onUpdate
}: {
  canEdit: boolean;
  canRoll: boolean;
  character: CharacterCard;
  onRoll: (label: string, targetValue: number, bonusPenalty?: number) => Promise<void>;
  onUpdate: (
    characterId: string,
    basic: Record<string, string>,
    attributes: Array<{ key: string; value: number | null }>,
    keeperNotes: string
  ) => Promise<void>;
}) {
  const [skillSearch, setSkillSearch] = useState("");
  const [showAllSkills, setShowAllSkills] = useState(false);
  const visibleSkills = (() => {
    let filtered = skillSearch
      ? character.skills.filter((s) => s.name.toLowerCase().includes(skillSearch.toLowerCase()))
      : character.skills.filter((s) => s.value != null);
    if (!showAllSkills && !skillSearch) filtered = filtered.slice(0, 24);
    return filtered;
  })();
  const name = character.basic.name || character.sourceFileName;
  const [editing, setEditing] = useState(false);
  const [basicDraft, setBasicDraft] = useState({
    name: character.basic.name || "",
    occupation: character.basic.occupation || "",
    age: character.basic.age || "",
    gender: character.basic.gender || ""
  });
  const [attributeDrafts, setAttributeDrafts] = useState<Record<string, string>>(() =>
    Object.fromEntries(character.attributes.map((attribute) => [attribute.key, String(attribute.value ?? "")]))
  );
  const [keeperNotes, setKeeperNotes] = useState(character.keeperNotes || "");
  const [lockedFields, setLockedFields] = useState<string[]>(character.lockedFields ?? []);
  const [statusDrafts, setStatusDrafts] = useState<Record<string, number | null>>(() => {
    const s: Record<string, number | null> = {};
    for (const [k, v] of Object.entries(character.status)) {
      s[k] = v as number | null;
    }
    return s;
  });
  const toggleLockedField = (field: string) => {
    setLockedFields((prev) =>
      prev.includes(field) ? prev.filter((f) => f !== field) : [...prev, field]
    );
  };

  function beginEdit() {
    setBasicDraft({
      name: character.basic.name || "",
      occupation: character.basic.occupation || "",
      age: character.basic.age || "",
      gender: character.basic.gender || ""
    });
    setAttributeDrafts(
      Object.fromEntries(character.attributes.map((attribute) => [attribute.key, String(attribute.value ?? "")]))
    );
    setKeeperNotes(character.keeperNotes || "");
    setEditing(true);
  }

  async function saveEdit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    await onUpdate(
      character.id,
      basicDraft,
      character.attributes.map((attribute) => ({
        key: attribute.key,
        value: attributeDrafts[attribute.key] ? Number(attributeDrafts[attribute.key]) : null
      })),
      keeperNotes
    );
    setEditing(false);
  }

  return (
    <article className="character-card">
      <div className="character-card__header">
        <div>
          <p className="panel__kicker">{character.ownerName}</p>
          <h2>{name}</h2>
          <p>
            {character.basic.occupation || "未读取职业"} · {character.basic.age || "年龄未知"}
          </p>
        </div>
        <span>{character.sourceFileName}</span>
      </div>

      {canEdit ? (
        <div className="character-actions">
          <button className="text-button" onClick={beginEdit} type="button">
            KP 编辑
          </button>
        </div>
      ) : null}

      {editing ? (
        <form className="character-editor" onSubmit={saveEdit}>
          <div className="character-editor__grid">
            <label>??<input value={basicDraft.name} onChange={(event) => setBasicDraft((draft) => ({ ...draft, name: event.target.value }))} /></label>
            <label>??<input value={basicDraft.occupation} onChange={(event) => setBasicDraft((draft) => ({ ...draft, occupation: event.target.value }))} /></label>
            <label>??<input value={basicDraft.age} onChange={(event) => setBasicDraft((draft) => ({ ...draft, age: event.target.value }))} /></label>
            <label>??<input value={basicDraft.gender} onChange={(event) => setBasicDraft((draft) => ({ ...draft, gender: event.target.value }))} /></label>
          </div>
          <div className="attribute-editor">
            {character.attributes.map((attribute) => (
              <label key={attribute.key}>
                {attribute.key}
                <input inputMode="numeric" value={attributeDrafts[attribute.key] ?? ""} onChange={(event) => setAttributeDrafts((draft) => ({ ...draft, [attribute.key]: event.target.value }))} />
              </label>
            ))}
          </div>
          <div className="character-editor__locked">
            <p className="character-editor__locked-title">?????????????????</p>
            <div className="character-editor__locked-grid">
              {character.attributes.map((attr) => (
                <label key={attr.key} className="locked-toggle">
                  <input type="checkbox" checked={lockedFields.includes(attr.key)} onChange={() => toggleLockedField(attr.key)} />
                  <span>{attr.key}</span>
                </label>
              ))}
            </div>
          </div>
          <label>KP ??<textarea value={keeperNotes} onChange={(event) => setKeeperNotes(event.target.value)} /></label>
          <div className="character-editor__actions">
            <button className="button button--primary" type="submit">?????</button>
            <button className="button button--ghost" onClick={() => setEditing(false)} type="button">??</button>
          </div>
        </form>
      ) : null}

      {character.warnings.length ? (
        <div className="character-warnings">
          {character.warnings.map((warning) => (
            <p key={warning}>{warning}</p>
          ))}
        </div>
      ) : null}

      <div className="attribute-grid">
        {character.attributes.map((attribute) => (
          <div key={attribute.key}>
            <span>{attribute.key}</span>
            <strong>{attribute.value ?? "?"}</strong>
            <small>
              困难 {attribute.half ?? "?"} · 极难 {attribute.fifth ?? "?"}
            </small>
            <small>
              困难 {attribute.half ?? "?"} · 极难 {attribute.fifth ?? "?"}
            </small>
            {canRoll && attribute.value ? (
              <button
                className="inline-roll"
                onClick={() => onRoll(`${name} · ${attribute.label}`, attribute.value ?? 0)}
                type="button"
              >
                投掷
              </button>
            ) : null}
          </div>
        ))}
      </div>

      {Object.keys(character.status).length > 0 && (
        <div className="status-panel">
          {Object.entries(character.status).map(([key, val]) => {
            if (val == null) return null;
            const labels: Record<string, string> = {
              hp: "HP", san: "SAN", mp: "MP", mov: "MOV",
              db: "伤害加值", build: "体格", armor: "护甲"
            };
            const maxVal = character.initialStatus?.[key] ?? null;
            const pct = maxVal && typeof val === "number" && maxVal > 0 ? Math.round((val / maxVal) * 100) : null;
            const barColor = key === "hp" ? (pct != null && pct <= 25 ? "var(--danger)" : "var(--accent)")
              : key === "san" ? "#7c6ff7"
              : key === "mp" ? "#4fc3f7"
              : null;
            return (
              <div key={key} className="status-chip">
                <span className="status-chip__label">{labels[key] || key.toUpperCase()}</span>
                <span className="status-chip__value">
                  {val}{maxVal != null ? " / " + maxVal : ""}
                </span>
                {barColor && pct != null && (
                  <div className="status-chip__bar">
                    <div className="status-chip__bar-fill" style={{ width: Math.min(pct, 100) + "%", background: barColor }} />
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}

      <div className="character-card__split">
        <div>
          <h3>技能预览</h3>
          <div className="skill-search-wrap">
            <input
              className="skill-search-input"
              placeholder="????..."
              value={skillSearch}
              onChange={(e) => setSkillSearch(e.target.value)}
            />
          </div>
          <div className="skill-list">
            {visibleSkills.map((skill) => (
              <button
                disabled={!canRoll || !skill.value}
                key={`${skill.name}-${skill.value}`}
                onClick={() => skill.value && onRoll(`${name} · ${skill.name}`, skill.value)}
                type="button"
              >
                {skill.name} {skill.value ?? "?"}
              </button>
            ))}
          </div>
          {!skillSearch && !showAllSkills && character.skills.filter((s) => s.value != null).length > 24 && (
            <button className="text-button" onClick={() => setShowAllSkills(true)} type="button">
              ??????
            </button>
          )}
        </div>
        <div>
          <h3>背景</h3>
          <div className="bg-detail">
            {Object.entries(character.background).filter(([,v]) => v).map(([k, v]) => (
              <div key={k} className="bg-item">
                <span className="bg-item__label">{
  ({"appearance":"外貌描述","beliefs":"思想与信念","significantPeople":"重要之人","significantLocations":"意义非凡之地","treasuredPossessions":"宝贵之物","traits":"特质","injuriesScars":"伤口和瘤痕","phobiasManias":"恐惧症和躁狂症","name":"姓名","player":"玩家","occupation":"职业","age":"年龄","gender":"性别","era":"时代","residence":"住地","birthplace":"故乡"} as Record<string,string>)[k] || k
}</span>
                <span className="bg-item__value">{v}</span>
              </div>
            ))}
            {Object.values(character.background).every(v => !v) && <p className="muted">暂未读取到背景文本</p>}
          </div>

          {character.weapons && character.weapons.length > 0 && (
            <><h3>武器</h3>
            <div className="weapon-list">
              {character.weapons.map((w, i) => (
                <div key={i} className="weapon-row">
                  <span className="weapon-row__name">{w.name || "武器"}</span>
                  <span className="weapon-row__dmg">{w.damage || "??"}</span>
                  {canRoll && w.skill && (
                    <button className="inline-roll" onClick={() => {
                      const sn = String(w.skill || "");
                      const sk = character.skills.find(s => s.name === sn);
                      if (sk?.value) onRoll(name + " · " + sn, sk.value, 0);
                    }} type="button">投掷</button>
                  )}
                </div>
              ))}
            </div></>
          )}

          {character.spells && character.spells.length > 0 && (
            <><h3>法术</h3>
            <div className="bg-detail">
              {character.spells.map((s, i) => (
                <div key={i} className="bg-item">
                  <span className="bg-item__label">{s.name || "法术"}</span>
                  <span className="bg-item__value">{s.cost || ""}</span>
                </div>
              ))}
            </div></>
          )}

          {character.experiences && character.experiences.length > 0 && (
            <details className="character-history">
              <summary>调查员经历</summary>
              {character.experiences.map((exp, i) => (
                <p key={i} className="muted">{typeof exp === "string" ? exp : exp.text || JSON.stringify(exp)}</p>
              ))}
            </details>
          )}
          {character.keeperNotes ? <p className="keeper-notes">KP 备注：{character.keeperNotes}</p> : null}
        </div>
      </div>
    </article>
  );
}

function firstFilled(values: Record<string, string>) {
  return Object.values(values).find(Boolean) ?? "";
}

