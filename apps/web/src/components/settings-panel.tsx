"use client";

import { useCallback, useEffect, useState } from "react";
import type { CSSProperties } from "react";

type BackgroundKey = "black" | "graphite" | "green" | "blue" | "red";

type UserSettings = {
  background: BackgroundKey;
  voiceMaxDuration: number;
  voiceUploadSizeMB: number;
  diceSound: boolean;
  autoScrollChat: boolean;
};

const DEFAULTS: UserSettings = {
  background: "black",
  voiceMaxDuration: 0,
  voiceUploadSizeMB: 50,
  diceSound: false,
  autoScrollChat: true,
};

const STORAGE_KEY = "coc-yes.settings";

const BACKGROUNDS: Array<{ key: BackgroundKey; label: string; color: string }> = [
  { key: "black", label: "纯黑", color: "#0a0a0c" },
  { key: "graphite", label: "深灰", color: "#121214" },
  { key: "green", label: "墨绿", color: "#060f0a" },
  { key: "blue", label: "深蓝", color: "#060e1a" },
  { key: "red", label: "暗红", color: "#160608" },
];

let _cached: UserSettings | null = null;

export function loadSettings(): UserSettings {
  if (_cached) return _cached;
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (raw) { _cached = { ...DEFAULTS, ...JSON.parse(raw) as UserSettings }; return _cached; }
  } catch { /* ignore */ }
  _cached = { ...DEFAULTS };
  return _cached;
}

export function saveSettings(s: UserSettings) {
  _cached = s;
  window.localStorage.setItem(STORAGE_KEY, JSON.stringify(s));
  document.documentElement.dataset.background = s.background;
}

export type { UserSettings, BackgroundKey };

// ── Component ──

export function SettingsPanel() {
  const [settings, setSettings] = useState<UserSettings>({ ...DEFAULTS });
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    setSettings(loadSettings());
    setLoaded(true);
  }, []);

  const update = useCallback((patch: Partial<UserSettings>) => {
    setSettings(prev => {
      const next = { ...prev, ...patch };
      saveSettings(next);
      return next;
    });
  }, []);

  if (!loaded) return null;

  return (
    <div className="settings-panel">
      <div className="settings-panel__header">
        <h2>设置</h2>
      </div>

      <div className="settings-block">
        <h3>界面背景</h3>
        <div className="settings-block__swatches">
          {BACKGROUNDS.map(item => (
            <button
              key={item.key}
              className={settings.background === item.key ? "swatch swatch--active" : "swatch"}
              onClick={() => update({ background: item.key })}
              style={{ "--swatch": item.color } as CSSProperties}
              type="button"
            >
              <span />
              {item.label}
            </button>
          ))}
        </div>
      </div>

      <div className="settings-block">
        <h3>录音</h3>
        <div className="settings-block__field">
          <label>最长录制（秒，0=不限）</label>
          <input type="number" min={0} max={7200} step={60} value={settings.voiceMaxDuration}
            onChange={e => update({ voiceMaxDuration: Math.max(0, Number(e.target.value) || 0) })} />
        </div>
      </div>

      <div className="settings-block">
        <h3>聊天</h3>
        <label className="settings-block__toggle">
          <input type="checkbox" checked={settings.diceSound}
            onChange={e => update({ diceSound: e.target.checked })} />
          <span>骰子音效</span>
        </label>
        <label className="settings-block__toggle">
          <input type="checkbox" checked={settings.autoScrollChat}
            onChange={e => update({ autoScrollChat: e.target.checked })} />
          <span>自动滚动</span>
        </label>
      </div>

      <button className="button button--ghost button--sm" onClick={() => {
        saveSettings({ ...DEFAULTS });
        setSettings({ ...DEFAULTS });
      }} type="button">
        恢复默认
      </button>
    </div>
  );
}
