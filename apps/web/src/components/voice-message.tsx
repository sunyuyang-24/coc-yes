"use client";

import { useCallback, useRef, useState } from "react";
import { apiUrl } from "@/lib/api";

type Props = {
  url: string;
  roomId: string;
  duration: number;
};

export function VoiceMessage({ url, roomId, duration }: Props) {
  const [playing, setPlaying] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const audioRef = useRef<HTMLAudioElement | null>(null);

  const cleanupAudio = useCallback(() => {
    if (audioRef.current) {
      audioRef.current.pause();
      audioRef.current.removeAttribute("src");
      audioRef.current.load();
      audioRef.current = null;
    }
  }, []);

  const togglePlay = useCallback(async () => {
    if (!audioRef.current) {
      // 清理旧实例后再创建新实例，防止内存泄漏
      cleanupAudio();
      const audio = new Audio(apiUrl(url));
      audioRef.current = audio;

      audio.ontimeupdate = () => setCurrentTime(audio.currentTime);
      audio.onended = () => {
        setPlaying(false);
        setCurrentTime(0);
        cleanupAudio();
      };
      audio.onerror = () => {
        setPlaying(false);
        console.error("Failed to load audio");
        cleanupAudio();
      };

      audio.play().catch(console.error);
      setPlaying(true);
      return;
    }

    if (playing) {
      audioRef.current.pause();
      setPlaying(false);
    } else {
      audioRef.current.play().catch(console.error);
      setPlaying(true);
    }
  }, [url, playing, cleanupAudio]);

  const fmt = (s: number) =>
    `${String(Math.floor(s / 60)).padStart(2, "0")}:${String(Math.floor(s % 60)).padStart(2, "0")}`;

  // 安全计算进度百分比
  const progressPercent = duration > 0 ? (currentTime / duration) * 100 : 0;

  return (
    <div className="voice-msg">
      <button
        className={`voice-msg__play ${playing ? "voice-msg__play--active" : ""}`}
        onClick={togglePlay}
        type="button"
      >
        {playing ? (
          <span className="voice-msg__pause-icon">⏸</span>
        ) : (
          <span className="voice-msg__play-icon">▶</span>
        )}
      </button>

      <div className="voice-msg__bar">
        <div
          className="voice-msg__progress"
          style={{ width: `${progressPercent}%` }}
        />
      </div>

      <span className="voice-msg__time">
        {playing ? fmt(currentTime) : fmt(duration)}
      </span>
    </div>
  );
}
