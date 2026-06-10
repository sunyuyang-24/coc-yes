"use client";

import { useEffect, useState } from "react";
import type { CSSProperties } from "react";

type BackgroundKey = "black" | "graphite" | "green" | "blue" | "red";

const STORAGE_KEY = "coc-yes.background";

const BACKGROUNDS: Array<{
  key: BackgroundKey;
  label: string;
  color: string;
}> = [
  {
    key: "black",
    label: "纯黑",
    color: "#000000"
  },
  {
    key: "graphite",
    label: "深灰",
    color: "#141414"
  },
  {
    key: "green",
    label: "墨绿",
    color: "#07130d"
  },
  {
    key: "blue",
    label: "深蓝",
    color: "#07111f"
  },
  {
    key: "red",
    label: "暗红",
    color: "#1a0708"
  }
];

export function BackgroundPicker() {
  const [active, setActive] = useState<BackgroundKey>("black");

  useEffect(() => {
    const saved = window.localStorage.getItem(STORAGE_KEY) as BackgroundKey | null;
    const next: BackgroundKey = isBackgroundKey(saved) ? saved : "black";
    applyBackground(next);
    setActive(next);
  }, []);

  function chooseBackground(key: BackgroundKey) {
    applyBackground(key);
    setActive(key);
    window.localStorage.setItem(STORAGE_KEY, key);
  }

  return (
    <article className="panel background-picker">
      <p className="panel__kicker">Background</p>
      <h2>纯色界面</h2>
      <p>默认纯黑，也可以按个人偏好切换为其他纯色。设置会保存在当前浏览器。</p>
      <div className="background-picker__grid" aria-label="背景颜色选择">
        {BACKGROUNDS.map((item) => (
          <button
            aria-pressed={active === item.key}
            className={active === item.key ? "swatch swatch--active" : "swatch"}
            key={item.key}
            onClick={() => chooseBackground(item.key)}
            style={{ "--swatch": item.color } as CSSProperties}
            type="button"
          >
            <span />
            {item.label}
          </button>
        ))}
      </div>
    </article>
  );
}

function applyBackground(key: BackgroundKey) {
  document.documentElement.dataset.background = key;
}

function isBackgroundKey(value: string | null): value is BackgroundKey {
  return BACKGROUNDS.some((item) => item.key === value);
}
