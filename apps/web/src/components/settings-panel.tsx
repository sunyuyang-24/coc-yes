"use client";

import { useCallback, useEffect, useState } from "react";
import type { CSSProperties } from "react";

type BackgroundKey = "black" | "graphite" | "green" | "blue" | "red" | "custom";

type BackgroundMode = "cover" | "contain" | "repeat" | "stretch" | "center";
type CustomBgKind = "color" | "image";

type CustomBackground = {
  kind: CustomBgKind;       // 颜色 / 图片 二选一
  color: string;            // 纯色模式：背景色；图片模式：底色（图片透明时透出）
  image?: string;           // data URL (图片模式才有效)
  mode: BackgroundMode;     // 图片显示模式
  opacity: number;          // 图片透明度 (0-1)
};

type UserSettings = {
  background: BackgroundKey;
  customBg: CustomBackground;
  voiceMaxDuration: number;
  voiceUploadSizeMB: number;
  diceSound: boolean;
  autoScrollChat: boolean;
};

const DEFAULTS: UserSettings = {
  background: "black",
  customBg: { kind: "color", color: "#0A0A0A", image: "", mode: "cover", opacity: 1 },
  voiceMaxDuration: 0,
  voiceUploadSizeMB: 50,
  diceSound: false,
  autoScrollChat: true,
};

const STORAGE_KEY = "coc-yes.settings";

const BACKGROUNDS: Array<{ key: BackgroundKey; label: string; color: string }> = [
  { key: "black", label: "纯黑", color: "#000000" },
  { key: "graphite", label: "深灰", color: "#141414" },
  { key: "green", label: "墨绿", color: "#0A1210" },
  { key: "blue", label: "深蓝", color: "#0A1018" },
  { key: "red", label: "暗红", color: "#140A0C" },
  { key: "custom", label: "自定义", color: "#0A0A0A" },
];

const BG_MODES: Array<{ key: BackgroundMode; label: string }> = [
  { key: "cover", label: "铺满" },
  { key: "contain", label: "适配" },
  { key: "repeat", label: "平铺" },
  { key: "stretch", label: "拉伸" },
  { key: "center", label: "居中" },
];

let _cached: UserSettings | null = null;

export function loadSettings(): UserSettings {
  if (_cached) return _cached;
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (raw) {
      const parsed = JSON.parse(raw) as Partial<UserSettings>;
      // 深合并 customBg，确保迁移老版本（无 kind 字段）
      const merged: UserSettings = {
        ...DEFAULTS,
        ...parsed,
        customBg: { ...DEFAULTS.customBg, ...(parsed.customBg || {}) },
      };
      // 如果没有 kind（老版本），根据有无 image 推断
      if (!merged.customBg.kind) {
        merged.customBg.kind = merged.customBg.image ? "image" : "color";
      }
      _cached = merged;
      return _cached;
    }
  } catch { /* ignore */ }
  _cached = { ...DEFAULTS };
  return _cached;
}

export function saveSettings(s: UserSettings) {
  _cached = s;
  window.localStorage.setItem(STORAGE_KEY, JSON.stringify(s));
  document.documentElement.dataset.background = s.background;
  document.documentElement.style.setProperty("--custom-bg-color", s.customBg.color);
  document.documentElement.dataset.customBgKind = s.customBg.kind;
  // 延迟通知：避免在 SettingsPanel 事件处理期间触发其他组件的 setState
  if (_layerListeners.length > 0) {
    queueMicrotask(() => {
      for (const fn of _layerListeners) fn(s);
    });
  }
}

export type { UserSettings, BackgroundKey, BackgroundMode, CustomBackground, CustomBgKind };

// ── 全局背景图层 ──
// 在 <main class="shell"> 内渲染一个 fixed div；完全通过 inline style 控制，
// 避免与现有的 --bg / background-color 冲突。

const MODE_STYLE: Record<BackgroundMode, { size: string; repeat: string; position: string }> = {
  cover:   { size: "cover",                repeat: "no-repeat", position: "center center" },
  contain: { size: "contain",              repeat: "no-repeat", position: "center center" },
  repeat:  { size: "auto",                 repeat: "repeat",    position: "top left" },
  stretch: { size: "100% 100%",            repeat: "no-repeat", position: "center center" },
  center:  { size: "auto",                 repeat: "no-repeat", position: "center center" },
};

let _layerListeners: Array<(s: UserSettings) => void> = [];

export function _subscribeSettings(fn: (s: UserSettings) => void): () => void {
  _layerListeners.push(fn);
  return () => { _layerListeners = _layerListeners.filter(x => x !== fn); };
}

/** Background layer component — reads settings on mount + whenever they change. */
export function CustomBackgroundLayer() {
  const [settings, setSettings] = useState<UserSettings | null>(null);

  useEffect(() => {
    const refresh = () => setSettings(loadSettings());
    refresh();
    const unsub = _subscribeSettings(refresh);
    const onStorage = (e: StorageEvent) => { if (e.key === STORAGE_KEY) refresh(); };
    window.addEventListener("storage", onStorage);
    return () => { unsub(); window.removeEventListener("storage", onStorage); };
  }, []);

  if (!settings || settings.background !== "custom") return null;

  const bg = settings.customBg;

  // 图片模式：渲染一个全屏 fixed 图片图层（置于最底层）
  if (bg.kind === "image" && bg.image) {
    const style = MODE_STYLE[bg.mode];
    const layerStyle: CSSProperties = {
      position: "fixed",
      inset: 0,
      zIndex: 0,
      backgroundImage: `url("${bg.image}")`,
      backgroundSize: style.size,
      backgroundRepeat: style.repeat,
      backgroundPosition: style.position,
      opacity: bg.opacity,
      pointerEvents: "none",
    };
    return <div aria-hidden className="custom-bg-layer" style={layerStyle} />;
  }

  return null;
}

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
              style={{
                "--swatch": item.key === "custom"
                  ? `linear-gradient(135deg, ${settings.customBg.color}, #000)`
                  : item.color,
              } as CSSProperties}
              type="button"
            >
              <span />
              {item.label}
            </button>
          ))}
        </div>

        {settings.background === "custom" && (
          <div className="settings-custom-bg">
            <div className="settings-block__field">
              <label>自定义模式</label>
              <div className="field-row">
                <button
                  type="button"
                  className={settings.customBg.kind === "color"
                    ? "button button--primary button--sm"
                    : "button button--ghost button--sm"}
                  onClick={() => update({ customBg: { ...settings.customBg, kind: "color" } })}
                >
                  纯色
                </button>
                <button
                  type="button"
                  className={settings.customBg.kind === "image"
                    ? "button button--primary button--sm"
                    : "button button--ghost button--sm"}
                  onClick={() => update({ customBg: { ...settings.customBg, kind: "image" } })}
                >
                  图片
                </button>
              </div>
            </div>

            {settings.customBg.kind === "color" && (
              <div className="settings-block__field">
                <label>背景颜色</label>
                <div className="field-row">
                  <input
                    type="color"
                    value={settings.customBg.color}
                    onChange={e => update({ customBg: { ...settings.customBg, color: e.target.value } })}
                  />
                  <input
                    type="text"
                    value={settings.customBg.color}
                    onChange={e => update({ customBg: { ...settings.customBg, color: e.target.value } })}
                    placeholder="#RRGGBB"
                    className="text-input"
                  />
                </div>
              </div>
            )}

            {settings.customBg.kind === "image" && (
              <>
                <div className="settings-block__field">
                  <label>背景图片</label>
                  <div className="field-row">
                    <label className="button button--ghost button--sm" style={{ cursor: "pointer" }}>
                      选择图片
                      <input
                        type="file"
                        accept="image/png, image/jpeg, image/webp, image/gif"
                        style={{ display: "none" }}
                        onChange={e => {
                          const file = e.target.files?.[0];
                          if (!file) return;
                          if (file.size > 8 * 1024 * 1024) {
                            alert("图片过大，请选择小于 8MB 的图片");
                            return;
                          }
                          const reader = new FileReader();
                          reader.onload = () => {
                            update({ customBg: { ...settings.customBg, image: String(reader.result) } });
                          };
                          reader.readAsDataURL(file);
                        }}
                      />
                    </label>
                    {settings.customBg.image ? (
                      <button
                        type="button"
                        className="button button--ghost button--sm"
                        onClick={() => update({ customBg: { ...settings.customBg, image: "" } })}
                      >
                        移除图片
                      </button>
                    ) : (
                      <span style={{ fontSize: 12, color: "var(--text-muted)" }}>未选择图片</span>
                    )}
                  </div>
                </div>

                <div className="settings-block__field">
                  <label>底色（图片透明或不完整时可见）</label>
                  <div className="field-row">
                    <input
                      type="color"
                      value={settings.customBg.color}
                      onChange={e => update({ customBg: { ...settings.customBg, color: e.target.value } })}
                    />
                    <input
                      type="text"
                      value={settings.customBg.color}
                      onChange={e => update({ customBg: { ...settings.customBg, color: e.target.value } })}
                      placeholder="#RRGGBB"
                      className="text-input"
                    />
                  </div>
                </div>

                <div className="settings-block__field">
                  <label>显示模式</label>
                  <div className="field-row field-row--wrap">
                    {BG_MODES.map(mode => (
                      <button
                        key={mode.key}
                        type="button"
                        className={settings.customBg.mode === mode.key
                          ? "button button--primary button--sm"
                          : "button button--ghost button--sm"}
                        onClick={() => update({ customBg: { ...settings.customBg, mode: mode.key } })}
                      >
                        {mode.label}
                      </button>
                    ))}
                  </div>
                </div>

                <div className="settings-block__field">
                  <label>图片透明度 {Math.round(settings.customBg.opacity * 100)}%</label>
                  <input
                    type="range"
                    min={0}
                    max={1}
                    step={0.05}
                    value={settings.customBg.opacity}
                    onChange={e => update({ customBg: { ...settings.customBg, opacity: Number(e.target.value) } })}
                  />
                </div>
              </>
            )}
          </div>
        )}
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
