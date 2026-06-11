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

  const startRecording = useCallback(async () => {
    try {
      const s = loadSettings();
      maxDurationRef.current = s.voiceMaxDuration;
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const recorder = new MediaRecorder(stream, {
        mimeType: MediaRecorder.isTypeSupported("audio/webm;codecs=opus")
          ? "audio/webm;codecs=opus"
          : "audio/webm",
      });

      chunksRef.current = [];
      recorder.ondataavailable = (e) => {
        if (e.data.size > 0) chunksRef.current.push(e.data);
      };

      recorder.onstop = async () => {
        stream.getTracks().forEach((t) => t.stop());
        const blob = new Blob(chunksRef.current, { type: recorder.mimeType });
        await uploadVoice(blob);
      };

      recorder.start();
      mediaRecorderRef.current = recorder;
      setState("recording");
      setElapsed(0);

      timerRef.current = setInterval(() => {
        setElapsed((prev) => {
          const next = prev + 1;
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

  const uploadVoice = async (blob: Blob) => {
    const form = new FormData();
    form.append("senderId", memberId);
    form.append("duration", String(elapsed));
    form.append("file", blob, `recording-${Date.now()}.webm`);

    try {
      await fetch(apiUrl(`/api/rooms/${roomId}/voice`), {
        method: "POST",
        body: form,
      });
      onSent?.();
    } catch (err) {
      console.error("Failed to upload voice:", err);
    } finally {
      setState("idle");
    }
  };

  const cancel = () => {
    mediaRecorderRef.current?.stop();
    if (timerRef.current) {
      clearInterval(timerRef.current);
      timerRef.current = null;
    }
    setState("idle");
  };

  return (
    <div className="voice-recorder">
      {state === "idle" && (
        <button
          className="voice-recorder__btn"
          onClick={startRecording}
          type="button"
          title="开始录音"
        >
          <span className="voice-recorder__icon">&#x1F399;</span>
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