"use client";

import { useCallback, useEffect, useState } from "react";
import type { CSSProperties } from "react";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

type BackgroundKey = "black" | "graphite" | "green" | "blue" | "red";

type UserSettings = {
  background: BackgroundKey;
  voiceMaxDuration: number;  // seconds, 0 = no limit
  voiceUploadSizeMB: number; // MB, 0 = no limit
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

// ---------------------------------------------------------------------------
// Background data
// ---------------------------------------------------------------------------

const BACKGROUNDS: Array<{ key: BackgroundKey; label: string; color: string }> = [
  { key: "black", label: "纯黑", color: "#000000" },
  { key: "graphite", label: "深灰", color: "#141414" },
  { key: "green", label: "墨绿", color: "#07130d" },
  { key: "blue", label: "深蓝", color: "#07111f" },
  { key: "red", label: "暗红", color: "#1a0708" },
];

// ---------------------------------------------------------------------------
// Shared helpers (also used by other components via settings context)
// ---------------------------------------------------------------------------

let _cached: UserSettings | null = null;

export function loadSettings(): UserSettings {
  if (_cached) return _cached;
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (raw) {
      const parsed = JSON.parse(raw) as Partial<UserSettings>;
      _cached = { ...DEFAULTS, ...parsed };
      return _cached;
    }
  } catch { /* ignore */ }
  _cached = { ...DEFAULTS };
  return _cached;
}

export function saveSettings(settings: UserSettings) {
  _cached = settings;
  window.localStorage.setItem(STORAGE_KEY, JSON.stringify(settings));
  applyBackground(settings.background);
}

// We export the raw read/write so VoiceRecorder can use voiceMaxDuration
export { STORAGE_KEY, DEFAULTS };
export type { UserSettings, BackgroundKey };

// ---------------------------------------------------------------------------
// Background apply
// ---------------------------------------------------------------------------

function applyBackground(key: BackgroundKey) {
  document.documentElement.dataset.background = key;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function SettingsPanel() {
  const [settings, setSettings] = useState<UserSettings>({ ...DEFAULTS });
  const [loaded, setLoaded] = useState(false);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    setSettings(loadSettings());
    setLoaded(true);
  }, []);

  const update = useCallback((patch: Partial<UserSettings>) => {
    setSettings((prev) => {
      const next = { ...prev, ...patch };
      saveSettings(next);
      return next;
    });
    setSaved(true);
    setTimeout(() => setSaved(false), 1500);
  }, []);

  if (!loaded) return null;

  return (
    <section className="settings-panel" id="settings">
      <div className="settings-panel__header">
        <h2>设置</h2>
        {saved && <span className="settings-panel__saved">已保存</span>}
      </div>

      {/* ---- Background ---- */}
      <div className="settings-block">
        <h3>界面背景</h3>
        <p className="settings-block__desc">默认纯黑，可切换为其他纯色。设置保存在当前浏览器。</p>
        <div className="settings-block__swatches">
          {BACKGROUNDS.map((item) => (
            <button
              aria-pressed={settings.background === item.key}
              className={settings.background === item.key ? "swatch swatch--active" : "swatch"}
              key={item.key}
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

      {/* ---- Voice Recording ---- */}
      <div className="settings-block">
        <h3>录音设置</h3>

        <div className="settings-block__row">
          <div className="settings-block__field">
            <label htmlFor="voiceMaxDuration">最长录音时长（秒，0 = 不限制）</label>
            <input
              id="voiceMaxDuration"
              type="number"
              min={0}
              max={7200}
              step={60}
              value={settings.voiceMaxDuration}
              onChange={(e) => update({ voiceMaxDuration: Math.max(0, Number(e.target.value) || 0) })}
            />
            <span className="settings-block__hint">
              {settings.voiceMaxDuration === 0
                ? "无限制"
                : `${Math.floor(settings.voiceMaxDuration / 60)} 分 ${settings.voiceMaxDuration % 60} 秒`}
            </span>
          </div>

          <div className="settings-block__field">
            <label htmlFor="voiceUploadSizeMB">上传大小上限（MB，0 = 默认 50MB）</label>
            <input
              id="voiceUploadSizeMB"
              type="number"
              min={0}
              max={500}
              step={5}
              value={settings.voiceUploadSizeMB}
              onChange={(e) => update({ voiceUploadSizeMB: Math.max(0, Number(e.target.value) || 0) })}
            />
            <span className="settings-block__hint">
              {settings.voiceUploadSizeMB === 0 ? "默认 50MB" : `${settings.voiceUploadSizeMB} MB`}
            </span>
          </div>
        </div>
      </div>

      {/* ---- Chat ---- */}
      <div className="settings-block">
        <h3>聊天设置</h3>

        <div className="settings-block__row">
          <label className="settings-block__toggle">
            <input
              type="checkbox"
              checked={settings.autoScrollChat}
              onChange={(e) => update({ autoScrollChat: e.target.checked })}
            />
            <span>新消息自动滚动到底部</span>
          </label>

          <label className="settings-block__toggle">
            <input
              type="checkbox"
              checked={settings.diceSound}
              onChange={(e) => update({ diceSound: e.target.checked })}
            />
            <span>投骰音效（待实现）</span>
          </label>
        </div>
      </div>

      {/* ---- Reset ---- */}
      <div className="settings-block">
        <button
          className="button button--ghost"
          onClick={() => {
            const def = { ...DEFAULTS };
            setSettings(def);
            saveSettings(def);
            setSaved(true);
            setTimeout(() => setSaved(false), 1500);
          }}
          type="button"
        >
          恢复默认设置
        </button>
      </div>
    </section>
  );
}