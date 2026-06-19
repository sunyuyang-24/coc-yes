"use client";

import type { FormEvent } from "react";
import { useState } from "react";
import type { CharacterCard } from "@coc-yes/shared";
import { STATUS_LABELS } from "@coc-yes/shared";

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
    keeperNotes: string,
    lockedFields: string[],
    status: Record<string, number | null>
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
    setStatusDrafts(() => {
      const s: Record<string, number | null> = {};
      for (const [k, v] of Object.entries(character.status)) s[k] = v as number | null;
      return s;
    });
    setLockedFields(character.lockedFields ?? []);
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
      keeperNotes,
      lockedFields,
      statusDrafts
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
      ) : !canEdit && canRoll ? (
        <div className="character-actions">
          <button className="text-button" onClick={() => {
            const msg = "请求修改角色卡: " + name;
            navigator.clipboard.writeText(msg).catch(() => {});
            alert("已复制到剪贴板，请向 KP 发送: " + msg);
          }} type="button">
            ✎ 请求更新角色卡
          </button>
        </div>
      ) : null}

      {editing ? (
        <form className="character-editor" onSubmit={saveEdit}>
          <div className="character-editor__grid">
            <label>姓名<input value={basicDraft.name} onChange={(event) => setBasicDraft((draft) => ({ ...draft, name: event.target.value }))} /></label>
            <label>职业<input value={basicDraft.occupation} onChange={(event) => setBasicDraft((draft) => ({ ...draft, occupation: event.target.value }))} /></label>
            <label>年龄<input value={basicDraft.age} onChange={(event) => setBasicDraft((draft) => ({ ...draft, age: event.target.value }))} /></label>
            <label>性别<input value={basicDraft.gender} onChange={(event) => setBasicDraft((draft) => ({ ...draft, gender: event.target.value }))} /></label>
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
            <p className="character-editor__locked-title">锁定字段（锁定后玩家无法查看对应属性值）</p>
            <div className="character-editor__locked-grid">
              {character.attributes.map((attr) => (
                <label key={attr.key} className="locked-toggle">
                  <input type="checkbox" checked={lockedFields.includes(attr.key)} onChange={() => toggleLockedField(attr.key)} />
                  <span>{attr.key}</span>
                </label>
              ))}
            </div>
          </div>
          <label>KP 备注<textarea value={keeperNotes} onChange={(event) => setKeeperNotes(event.target.value)} /></label>
          <div className="character-editor__actions">
            <button className="button button--primary" type="submit">保存修改</button>
            <button className="button button--ghost" onClick={() => setEditing(false)} type="button">取消</button>
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

      <div className="status-panel">
          {Object.entries(character.status).map(([key, val]) => {
            if (val == null) return null;
            const label = STATUS_LABELS[key];
            if (!label) return null;
            const maxVal = character.initialStatus?.[key] ?? null;
            const pct = maxVal && typeof val === "number" && maxVal > 0 ? Math.round((val / maxVal) * 100) : null;
            const barColor = key === "hp" ? (pct != null && pct <= 25 ? "var(--danger)" : "var(--accent)")
              : key === "san" ? "#7c6ff7"
              : null;
            return (
              <div key={key} className="status-chip">
                <span className="status-chip__label">{label}</span>
                <span className="status-chip__value">
                  {maxVal != null ? maxVal + " / " : ""}{val}
                </span>
                {barColor && pct != null && (
                  <div className="status-chip__bar">
                    <div className="status-chip__bar-fill" style={{ width: Math.min(pct, 100) + "%", background: barColor }} />
                  </div>
                )}
              </div>
            );
          })}
          {/* Luck — fallback to attributes for pre-existing characters */}
          {(() => {
            const luckVal = character.status.luck ?? character.attributes?.find((a) => a.key === "LUCK")?.value;
            if (luckVal == null) return null;
            const luckMax = character.initialStatus?.luck ?? luckVal;
            return (
              <div key="luck" className="status-chip">
                <span className="status-chip__label">幸运</span>
                <span className="status-chip__value">
                  {luckMax} / {luckVal}
                </span>
                <div className="status-chip__bar">
                  <div className="status-chip__bar-fill" style={{
                    width: Math.min((luckVal / (luckMax || 1)) * 100, 100) + "%",
                    background: "#FFD54F" }} />
                </div>
              </div>
            );
          })()}
        </div>

      <div className="character-card__split">
        <div className="char-card__section">
          <h4>技能 ({character.skills.filter(s => s.value != null).length})</h4>
          <div className="skill-search-wrap">
            <input
              className="skill-search-input"
              placeholder="搜索技能..."
              value={skillSearch}
              onChange={(e) => setSkillSearch(e.target.value)}
            />
          </div>
          <div className="char-card__skills">
            {visibleSkills.map((skill) => (
              <div
                key={`${skill.name}-${skill.value}`}
                className="char-card__skill"
                onClick={() => skill.value && canRoll && onRoll(`${name} · ${skill.name}`, skill.value)}
                title={skill.value ? `${skill.name} 常规 ${skill.value} / 困难 ${skill.half ?? "?"} / 极难 ${skill.fifth ?? "?"}` : undefined}
                style={{ cursor: canRoll && skill.value ? "pointer" : "default", opacity: skill.value ? 1 : 0.4 }}
              >
                <div style={{ display: "flex", flexDirection: "column", gap: "2px", flex: 1, minWidth: 0 }}>
                  <span className="char-card__skill-name">{skill.name}</span>
                  <span style={{ fontSize: "10px", color: "var(--text-muted)" }}>
                    困难 {skill.half ?? "?"} · 极难 {skill.fifth ?? "?"}
                  </span>
                </div>
                <span className="char-card__skill-val">{skill.value ?? "?"}</span>
              </div>
            ))}
          </div>
          {!skillSearch && !showAllSkills && character.skills.filter((s) => s.value != null).length > 24 && (
            <button className="text-button" onClick={() => setShowAllSkills(true)} type="button" style={{ marginTop: "8px", width: "100%" }}>
              显示全部 ({character.skills.filter(s => s.value != null).length})
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


