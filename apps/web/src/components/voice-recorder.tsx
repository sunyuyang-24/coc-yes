"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { loadSettings, type UserSettings } from "@/components/settings-panel";
import { apiUrl } from "@/lib/api";

type Props = {
  roomId: string;
  memberId: string;
  onSent?: () => void;
};

export function VoiceRecorder({ roomId, memberId, onSent }: Props) {
  const [state, setState] = useState<"idle" | "recording" | "uploading">("idle");
  const [elapsed, setElapsed] = useState(0);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const maxDurationRef = useRef(0);
  /** 使用 ref 记录实际录制时长，避免闭包过期 */
  const elapsedRef = useRef(0);

  const startRecording = useCallback(async () => {
    try {
      const s = loadSettings();
      maxDurationRef.current = s.voiceMaxDuration;
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });

      // Safar 兼容：优先检测 audio/mp4
      const mimeType = MediaRecorder.isTypeSupported("audio/webm;codecs=opus")
        ? "audio/webm;codecs=opus"
        : MediaRecorder.isTypeSupported("audio/mp4")
          ? "audio/mp4"
          : "audio/webm";

      const recorder = new MediaRecorder(stream, { mimeType });

      chunksRef.current = [];
      recorder.ondataavailable = (e) => {
        if (e.data.size > 0) chunksRef.current.push(e.data);
      };

      recorder.onstop = () => {
        stream.getTracks().forEach((t) => t.stop());
        const blob = new Blob(chunksRef.current, { type: recorder.mimeType });
        uploadVoice(blob);
      };

      recorder.start();
      mediaRecorderRef.current = recorder;
      setState("recording");
      setElapsed(0);
      elapsedRef.current = 0;

      timerRef.current = setInterval(() => {
        setElapsed((prev) => {
          const next = prev + 1;
          elapsedRef.current = next;
          const limit = maxDurationRef.current;
          if (limit > 0 && next >= limit) {
            mediaRecorderRef.current?.stop();
            if (timerRef.current) clearInterval(timerRef.current);
            return limit;
          }
          return next;
        });
      }, 1000);
    } catch (err) {
      console.error("Failed to start recording:", err);
    }
  }, [roomId, memberId]);

  const stopRecording = useCallback(() => {
    mediaRecorderRef.current?.stop();
    if (timerRef.current) {
      clearInterval(timerRef.current);
      timerRef.current = null;
    }
    setState("uploading");
  }, []);

  /** 上传语音，支持重试和超时 */
  const uploadVoice = async (blob: Blob, retries = 3) => {
    const form = new FormData();
    form.append("senderId", memberId);
    // 使用 ref 获取实际录制时长，避免闭包过期
    form.append("duration", String(elapsedRef.current));
    form.append("file", blob, `recording-${Date.now()}.webm`);

    for (let attempt = 0; attempt < retries; attempt++) {
      try {
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 30000);

        const res = await fetch(apiUrl(`/api/rooms/${roomId}/voice`), {
          method: "POST",
          body: form,
          signal: controller.signal,
        });

        clearTimeout(timeoutId);
        if (res.ok) {
          onSent?.();
          break;
        }
        // 非 2xx 响应，等待后重试
        if (attempt < retries - 1) {
          await new Promise(r => setTimeout(r, 2000 * (attempt + 1)));
        }
      } catch (err) {
        console.error(`Upload attempt ${attempt + 1} failed:`, err);
        if (attempt < retries - 1) {
          await new Promise(r => setTimeout(r, 2000 * (attempt + 1)));
        }
      }
    }
    setState("idle");
  };

  const cancel = () => {
    mediaRecorderRef.current?.stop();
    if (timerRef.current) {
      clearInterval(timerRef.current);
      timerRef.current = null;
    }
    setState("idle");
  };

  // 组件卸载时清理录音资源
  useEffect(() => {
    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
      if (mediaRecorderRef.current && mediaRecorderRef.current.state === "recording") {
        mediaRecorderRef.current.stop();
      }
    };
  }, []);

  return (
    <div className="voice-recorder">
      {state === "idle" && (
        <button
          className="voice-recorder__btn"
          onClick={startRecording}
          type="button"
          title="开始录音"
        >
          <span className="voice-recorder__icon">🎙</span>
        </button>
      )}

      {state === "recording" && (
        <div className="voice-recorder__active">
          <span className="voice-recorder__dot" />
          <span className="voice-recorder__timer">
            {String(Math.floor(elapsed / 60)).padStart(2, "0")}:
            {String(elapsed % 60).padStart(2, "0")}
          </span>
          <button
            className="voice-recorder__stop"
            onClick={stopRecording}
            type="button"
          >
            停止并发送
          </button>
          <button className="voice-recorder__cancel" onClick={cancel} type="button">
            取消
          </button>
        </div>
      )}

      {state === "uploading" && (
        <span className="voice-recorder__uploading">上传中...</span>
      )}
    </div>
  );
}
