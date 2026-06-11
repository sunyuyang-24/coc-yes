"use client";

import { useCallback, useEffect, useState } from "react";
import type { RoomDetail } from "@coc-yes/shared";
import { apiRequest, apiUrl } from "@/lib/api";

type Summary = {
  roomName: string;
  status: string;
  startedAt: string;
  endedAt: string;
  memberCount: number;
  characters: Array<{
    name: string;
    ownerName: string;
    occupation: string;
    status: Record<string, number | null>;
    keeperNotes: string;
  }>;
  messageCount: number;
  rollCount: number;
  voiceCount: number;
  keyRolls: Array<{
    rollerName: string;
    expression: string;
    total: number | null;
    successLabel: string;
    createdAt: string;
  }>;
  draft: string;
};

type Props = {
  room: RoomDetail;
  memberId: string;
  isKeeper: boolean;
};

export function SummaryPanel({ room, memberId, isKeeper }: Props) {
  const [summary, setSummary] = useState<Summary | null>(null);
  const [draft, setDraft] = useState("");
  const [saving, setSaving] = useState(false);
  const [notice, setNotice] = useState("");

  useEffect(() => {
    if (room.status !== "ended") return;
    apiRequest<{ summary: Summary }>(`/api/rooms/${room.id}/summary`)
      .then((resp) => {
        setSummary(resp.summary);
        setDraft(resp.summary.draft || generateDefaultDraft(resp.summary));
      })
      .catch((err) => setNotice("加载总结失败: " + err));
  }, [room.id, room.status]);

  const endRoom = useCallback(async () => {
    if (!isKeeper) return;
    const form = new FormData();
    form.append("editorId", memberId);
    try {
      await fetch(apiUrl(`/api/rooms/${room.id}/end`), {
        method: "POST",
        body: form,
      });
    } catch (err) {
      setNotice("结束房间失败: " + err);
    }
  }, [room.id, memberId, isKeeper]);

  const exportCopy = useCallback(() => {
    navigator.clipboard.writeText(draft).then(() => {
      setNotice("总结已复制到剪贴板！");
    }).catch(() => {
      setNotice("复制失败，请手动复制。");
    });
  }, [draft]);

  const exportDownload = useCallback(() => {
    const blob = new Blob([draft], { type: "text/markdown;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = room.name + "_summary.md";
    a.click();
    URL.revokeObjectURL(url);
    setNotice("总结已下载！");
  }, [draft, room.name]);

  const saveSummary = useCallback(async () => {
    if (!isKeeper) return;
    setSaving(true);
    const form = new FormData();
    form.append("editorId", memberId);
    form.append("draft", draft);
    try {
      await fetch(apiUrl(`/api/rooms/${room.id}/summary`), {
        method: "POST",
        body: form,
      });
      setNotice("总结已保存。");
    } catch (err) {
      setNotice("保存失败: " + err);
    } finally {
      setSaving(false);
    }
  }, [room.id, memberId, isKeeper, draft]);

  if (room.status !== "ended" && isKeeper) {
    return (
      <section className="summary-panel">
        <h3>跑团总结</h3>
        <p className="notice">跑团进行中。结束跑团后可以生成总结。</p>
        <button className="button button--primary" onClick={endRoom} type="button">
          结束跑团
        </button>
      </section>
    );
  }

  if (!summary) {
    return null;
  }

  return (
    <section className="summary-panel">
      <h3>跑团总结</h3>
      <div className="summary-panel__stats">
        <span>成员: {summary.memberCount}</span>
        <span>消息: {summary.messageCount}</span>
        <span>投掷: {summary.rollCount}</span>
        <span>语音: {summary.voiceCount}</span>
      </div>

      <div className="summary-panel__characters">
        <h4>角色状态</h4>
        {summary.characters.map((c) => (
          <div key={c.name} className="summary-char-card">
            <strong>{c.name}</strong>
            <span>{c.occupation} ({c.ownerName})</span>
            {c.keeperNotes && <p className="keeper-notes">KP: {c.keeperNotes}</p>}
          </div>
        ))}
      </div>

      {summary.keyRolls.length > 0 && (
        <div className="summary-panel__rolls">
          <h4>最近投掷</h4>
          <ul>
            {summary.keyRolls.slice(-10).reverse().map((r, i) => (
              <li key={i}>
                [{r.rollerName}] {r.expression} = {r.total ?? "?"}
                {r.successLabel ? ` — ${r.successLabel}` : ""}
              </li>
            ))}
          </ul>
        </div>
      )}

      {isKeeper && (
        <div className="summary-panel__editor">
          <h4>KP 编辑总结</h4>
          <textarea
            className="summary-editor"
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            placeholder="写下剧情概要、关键线索、玩家行动、角色状态变化和待办..."
            rows={12}
          />
          <div className="summary-panel__actions">
            <button
              className="button button--primary"
              onClick={saveSummary}
              disabled={saving}
              type="button"
            >
              {saving ? "保存中..." : "保存总结"}
            </button>
            <button
              className="button button--ghost"
              onClick={exportCopy}
              type="button"
            >
              复制总结
            </button>
            <button
              className="button button--ghost"
              onClick={exportDownload}
              type="button"
            >
              下载 .md
            </button>
          </div>
        </div>
      )}

      {!isKeeper && summary.draft && (
        <div className="summary-panel__draft">
          <h4>KP 总结</h4>
          <p>{draft}</p>
        </div>
      )}

      {notice && <p className="notice">{notice}</p>}
    </section>
  );
}

function generateDefaultDraft(summary: Summary): string {
  const lines: string[] = [];
  lines.push(`# ${summary.roomName} — 跑团总结`);
  lines.push("");
  lines.push("## 剧情概要");
  lines.push("（KP 在此记录本次跑团的剧情概要）");
  lines.push("");
  lines.push("## 关键线索");
  lines.push("（列出本次发现的线索）");
  lines.push("");
  lines.push("## 参与角色");
  for (const c of summary.characters) {
    lines.push(`- ${c.name}（${c.occupation}，${c.ownerName}）`);
  }
  lines.push("");
  lines.push("## 重要投掷");
  for (const r of summary.keyRolls.slice(-5).reverse()) {
    const label = r.expression;
    const result = r.total !== null ? `${r.total}` : "?";
    const success = r.successLabel ? ` — ${r.successLabel}` : "";
    lines.push(`- ${r.rollerName}: ${label} = ${result}${success}`);
  }
  lines.push("");
  lines.push("## 角色状态变化");
  lines.push("（记录本次跑团中的角色状态变化）");
  lines.push("");
  lines.push("## 待办");
  lines.push("（列出下次开团前需要处理的事项）");
  lines.push("");
  return lines.join("\n");
}