"use client";

import { useState } from "react";
import type { CharacterCard } from "@coc-yes/shared";
import { apiRequest } from "@/lib/api";

type Props = {
  roomId: string;
  character: CharacterCard;
  isKeeper: boolean;
  onClose: () => void;
};

export function SanCheckPanel({ roomId, character, isKeeper, onClose }: Props) {
  const [successLoss, setSuccessLoss] = useState("0");
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
          successLoss,
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
            <label>成功损失 <small>（通常为 0 或 1）</small></label>
            <input value={successLoss} onChange={(e) => setSuccessLoss(e.target.value)}
              placeholder="如: 0, 1, 1D3" />
            <small>意志检定成功时扣除的 SAN（CRB p155）</small>
          </div>

          <div className="san-check__field">
            <label>失败损失 <small>（骰子表达式）</small></label>
            <input value={failureLoss} onChange={(e) => setFailureLoss(e.target.value)}
              placeholder="如: 1D6, 1D10, 1D4+1" />
            <small>意志检定失败时扣除的 SAN（自动投掷该表达式）</small>
          </div>

          <div className="san-check__presets">
            <span style={{ fontSize: "11px", color: "var(--text-muted)" }}>快速:</span>
            {["0/1D6", "0/1", "0/1D3", "1/1D4", "1/1D6", "1D3/1D6", "1D4/1D10", "1D6/1D10", "1D6/1D20", "1D10/1D100"].map((preset) => (
              <button key={preset} type="button" className="dice-inline__preset"
                onClick={() => {
                  const [s, f] = preset.split("/");
                  setSuccessLoss(s);
                  setFailureLoss(f);
                }}>
                {preset}
              </button>
            ))}
          </div>

          {isKeeper && (
            <label style={{ fontSize: "12px", display: "flex", alignItems: "center", gap: "6px" }}>
              <input type="checkbox" checked={hidden} onChange={(e) => setHidden(e.target.checked)} />
              暗投（仅KP可见）
            </label>
          )}

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
