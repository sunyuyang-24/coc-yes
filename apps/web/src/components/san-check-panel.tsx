"use client";

import { useState } from "react";
import type { CharacterCard } from "@coc-yes/shared";
import { apiRequest } from "@/lib/api";
import { HiddenToggle } from "@/components/hidden-toggle";

type Props = {
  roomId: string;
  character: CharacterCard;
  isKeeper: boolean;
  onClose: () => void;
};

export function SanCheckPanel({ roomId, character, isKeeper, onClose }: Props) {
  const [failureLoss, setFailureLoss] = useState("1D6");
  const [hidden, setHidden] = useState(false);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState("");

  async function submit() {
    if (sending) return;
    setSending(true);
    setError("");
    try {
      await apiRequest(`/api/rooms/${roomId}/rolls/san-check`, {
        method: "POST",
        body: JSON.stringify({
          characterId: character.id,
          successLoss: "0",
          failureLoss,
          hidden: hidden && isKeeper,
        }),
      });
      onClose();
    } catch (err) {
      setError(`SAN检定失败: ${err instanceof Error ? err.message : "网络错误"}`);
    } finally {
      setSending(false);
    }
  }

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-panel" onClick={(e) => e.stopPropagation()} style={{ maxWidth: "440px" }}>
        <div className="modal-panel__header">
          <span className="modal-panel__title">SAN CHECK — {character.basic.name || "?"}</span>
          <button className="button button--ghost button--sm" onClick={onClose} type="button">✕</button>
        </div>

        <div style={{ display: "flex", flexDirection: "column", gap: "14px" }}>
          <div style={{ display: "flex", gap: "12px", alignItems: "center", padding: "8px 12px", background: "var(--bg-hover)", borderRadius: "var(--radius)" }}>
            <span style={{ fontSize: "13px", color: "var(--text-secondary)" }}>当前 SAN:</span>
            <span style={{ fontFamily: "var(--font-mono)", fontSize: "20px", fontWeight: 700, color: "#7C6FF7" }}>
              {character.status.san ?? "—"}
            </span>
          </div>

          <div className="san-check__field">
            <label>SAN 损失 <small>（骰子表达式，失败时扣除）</small></label>
            <input value={failureLoss} onChange={(e) => setFailureLoss(e.target.value)}
              placeholder="如: 1D6, 1D10, 1D4+1" />
            <small>意志检定失败时扣除的 SAN。检定成功时扣除 0。</small>
          </div>

          <div className="san-check__presets">
            <span style={{ fontSize: "11px", color: "var(--text-muted)" }}>快速:</span>
            {["1", "1D3", "1D4", "1D6", "1D10", "1D20", "1D100", "2D6", "2D10", "1D4+1"].map((preset) => (
              <button key={preset} type="button" className="dice-inline__preset"
                onClick={() => setFailureLoss(preset)}>
                {preset}
              </button>
            ))}
          </div>

          {isKeeper && <HiddenToggle checked={hidden} onChange={setHidden} label="暗投（仅KP可见）" />}

          {error && (
            <p style={{ color: "var(--error)", fontSize: "12px", textAlign: "center" }}>{error}</p>
          )}
          <div style={{ display: "flex", gap: "8px", justifyContent: "flex-end" }}>
            <button className="button button--ghost button--sm" onClick={onClose} type="button">取消</button>
            <button className="button button--primary" onClick={submit} disabled={sending} type="button">
              {sending ? "投掷中..." : "SAN 检定"}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
