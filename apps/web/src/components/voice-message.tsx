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

  const togglePlay = useCallback(async () => {
    if (!audioRef.current) {
      const audio = new Audio(apiUrl(url));
      audioRef.current = audio;

      audio.ontimeupdate = () => setCurrentTime(audio.currentTime);
      audio.onended = () => {
        setPlaying(false);
        setCurrentTime(0);
      };
      audio.onerror = () => {
        setPlaying(false);
        console.error("Failed to load audio");
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
  }, [url, playing]);

  const fmt = (s: number) =>
    `${String(Math.floor(s / 60)).padStart(2, "0")}:${String(Math.floor(s % 60)).padStart(2, "0")}`;

  return (
    <div className="voice-msg">
      <button
        className={`voice-msg__play ${playing ? "voice-msg__play--active" : ""}`}
        onClick={togglePlay}
        type="button"
      >
        {playing ? (
          <span className="voice-msg__pause-icon">&#x23F8;</span>
        ) : (
          <span className="voice-msg__play-icon">&#x25B6;</span>
        )}
      </button>

      <div className="voice-msg__bar">
        <div
          className="voice-msg__progress"
          style={{ width: `${duration > 0 ? (currentTime / duration) * 100 : 0}%` }}
        />
      </div>

      <span className="voice-msg__time">
        {playing ? fmt(currentTime) : fmt(duration)}
      </span>
    </div>
  );
}