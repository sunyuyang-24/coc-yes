"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { wsUrl } from "@/lib/api";

type VoicePeer = {
  memberId: string;
  displayName: string;
  connection: RTCPeerConnection;
  stream?: MediaStream;
  muted: boolean;
};

type Props = {
  roomId: string;
  memberId: string;
  memberName: string;
  memberNames?: Record<string, string>;
  /** 是否为 KP（守秘人），KP 拥有语音房间管理权限 */
  isKeeper?: boolean;
};

export function VoiceRoom({ roomId, memberId, memberName, memberNames, isKeeper }: Props) {
  const [joined, setJoined] = useState(false);
  const [peers, setPeers] = useState<VoicePeer[]>([]);
  const [muted, setMuted] = useState(false);
  const [allMuted, setAllMuted] = useState(false);
  const [audioDevices, setAudioDevices] = useState<MediaDeviceInfo[]>([]);
  const [selectedDevice, setSelectedDevice] = useState<string>("");
  const localStreamRef = useRef<MediaStream | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const peersRef = useRef<VoicePeer[]>([]);
  const abortControllersRef = useRef<Map<string, AbortController>>(new Map());
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const joiningRef = useRef(false);

  const updatePeers = useCallback((updater: (prev: VoicePeer[]) => VoicePeer[]) => {
    setPeers(prev => {
      const next = updater(prev);
      peersRef.current = next;
      return next;
    });
  }, []);

  // 枚举音频输入设备
  useEffect(() => {
    navigator.mediaDevices.enumerateDevices().then(devices => {
      setAudioDevices(devices.filter(d => d.kind === "audioinput"));
    });
  }, []);

  // Create peer connection
  const createPeer = useCallback((targetId: string, displayName: string, isPolite: boolean) => {
    const pc = new RTCPeerConnection({
      iceServers: [
        { urls: "stun:stun.l.google.com:19302" },
        // TURN 服务器 fallback（需要通过环境变量配置）
        ...(process.env.NEXT_PUBLIC_TURN_URL
          ? [{
              urls: process.env.NEXT_PUBLIC_TURN_URL,
              username: process.env.NEXT_PUBLIC_TURN_USER ?? "",
              credential: process.env.NEXT_PUBLIC_TURN_CRED ?? "",
            }]
          : []),
      ],
    });

    // Add local stream
    if (localStreamRef.current) {
      localStreamRef.current.getTracks().forEach(track => {
        pc.addTrack(track, localStreamRef.current!);
      });
    }

    // Handle remote stream
    pc.ontrack = (event) => {
      const stream = event.streams[0];
      updatePeers(prev =>
        prev.map(p => p.memberId === targetId ? { ...p, stream } : p)
      );
    };

    // Handle ICE candidates
    pc.onicecandidate = (event) => {
      if (event.candidate && wsRef.current?.readyState === WebSocket.OPEN) {
        wsRef.current.send(JSON.stringify({
          type: "webrtc_ice",
          target: targetId,
          candidate: event.candidate,
        }));
      }
    };

    // Polite peer initiates
    if (isPolite) {
      pc.createOffer().then(offer => {
        pc.setLocalDescription(offer);
        wsRef.current?.send(JSON.stringify({
          type: "webrtc_offer",
          target: targetId,
          sdp: offer,
        }));
      }).catch(console.error);
    }

    // 使用 AbortController 管理 peer 生命周期，避免竞态条件
    const abortController = new AbortController();
    abortControllersRef.current.set(targetId, abortController);

    // Track connection state with ICE restart
    pc.onconnectionstatechange = () => {
      if (abortController.signal.aborted) return;

      if (pc.connectionState === "failed") {
        // Attempt ICE restart before giving up
        if (isPolite) {
          pc.restartIce();
          pc.createOffer({ iceRestart: true }).then(offer => {
            pc.setLocalDescription(offer);
            wsRef.current?.send(JSON.stringify({
              type: "webrtc_offer",
              target: targetId,
              sdp: offer,
            }));
          }).catch(() => {
            updatePeers(prev => prev.filter(p => p.memberId !== targetId));
            pc.close();
          });
        } else {
          updatePeers(prev => prev.filter(p => p.memberId !== targetId));
          pc.close();
        }
      } else if (pc.connectionState === "disconnected") {
        // May recover via ICE restart, wait 5s
        const timeoutId = setTimeout(() => {
          if (abortController.signal.aborted) return;
          if (pc.connectionState === "disconnected") {
            updatePeers(prev => prev.filter(p => p.memberId !== targetId));
            pc.close();
          }
        }, 5000);
        abortController.signal.addEventListener("abort", () => clearTimeout(timeoutId));
      }
    };

    return pc;
  }, [updatePeers]);

  // 建立 WebSocket 信号连接（抽取为独立函数以便重连）
  const connectSignaling = useCallback(() => {
    const url = wsUrl("/api/rooms/" + roomId + "/ws") + "?member_id=" + encodeURIComponent(memberId);
    const ws = new WebSocket(url);
    wsRef.current = ws;

    ws.onopen = () => {
      ws.send(JSON.stringify({ type: "webrtc_voice_join" }));
    };

    ws.onmessage = (event) => {
      const msg = JSON.parse(event.data);
      if (!msg.type || !msg.type.startsWith("webrtc_")) return;

      const fromId = msg.from;
      if (fromId === memberId) return;

      switch (msg.type) {
        case "webrtc_voice_join": {
          // New peer joined - create connection (polite if our ID > theirs)
          const polite = memberId > fromId;
          const fromName = memberNames?.[fromId] || "成员";
          const pc = createPeer(fromId, fromName, polite);
          updatePeers(prev => {
            if (prev.find(p => p.memberId === fromId)) return prev;
            return [...prev, { memberId: fromId, displayName: fromName, connection: pc, muted: false }];
          });
          break;
        }
        case "webrtc_offer": {
          const existing = peersRef.current.find(p => p.memberId === fromId);
          const fromName = memberNames?.[fromId] || "成员";
          const pc = existing
            ? existing.connection
            : (() => {
                const newPc = createPeer(fromId, fromName, false);
                updatePeers(prev => [...prev, { memberId: fromId, displayName: fromName, connection: newPc, muted: false }]);
                return newPc;
              })();
          void pc.setRemoteDescription(new RTCSessionDescription(msg.sdp));
          void pc.createAnswer().then(answer => {
            pc.setLocalDescription(answer);
            wsRef.current?.send(JSON.stringify({
              type: "webrtc_answer",
              target: fromId,
              sdp: answer,
            }));
          }).catch(console.error);
          break;
        }
        case "webrtc_answer": {
          const peer = peersRef.current.find(p => p.memberId === fromId);
          if (peer?.connection.signalingState !== "stable") {
            peer?.connection.setRemoteDescription(new RTCSessionDescription(msg.sdp)).catch(console.error);
          }
          break;
        }
        case "webrtc_ice": {
          const peer = peersRef.current.find(p => p.memberId === fromId);
          if (peer && msg.candidate) {
            peer.connection.addIceCandidate(new RTCIceCandidate(msg.candidate)).catch(console.error);
          }
          break;
        }
        case "webrtc_voice_leave": {
          const peer = peersRef.current.find(p => p.memberId === fromId);
          peer?.connection.close();
          abortControllersRef.current.get(fromId)?.abort();
          updatePeers(prev => prev.filter(p => p.memberId !== fromId));
          break;
        }
        case "webrtc_mute":
        case "webrtc_unmute":
        case "webrtc_force_mute": {
          updatePeers(prev =>
            prev.map(p => p.memberId === fromId ? { ...p, muted: msg.type === "webrtc_mute" || msg.type === "webrtc_force_mute" } : p)
          );
          // If received force_mute, mute self
          if (msg.type === "webrtc_force_mute" && msg.target === memberId) {
            localStreamRef.current?.getAudioTracks().forEach(t => (t.enabled = false));
            setMuted(true);
          }
          break;
        }
      }
    };

    ws.onclose = () => {
      // Cleanup all peers
      peersRef.current.forEach(p => {
        p.connection.close();
        abortControllersRef.current.get(p.memberId)?.abort();
      });
      updatePeers(() => []);
      setJoined(false);
      joiningRef.current = false;
      localStreamRef.current?.getTracks().forEach(t => t.stop());
      localStreamRef.current = null;
    };

    ws.onerror = () => {
      // 清理旧的重连定时器，3秒后完全重建连接
      if (reconnectTimerRef.current) clearTimeout(reconnectTimerRef.current);
      reconnectTimerRef.current = setTimeout(() => {
        if (!localStreamRef.current) return;
        // 清理旧的 peer 连接后再重连
        peersRef.current.forEach(p => {
          p.connection.close();
          abortControllersRef.current.get(p.memberId)?.abort();
        });
        updatePeers(() => []);
        connectSignaling();
      }, 3000);
    };

    return ws;
  }, [roomId, memberId, memberNames, createPeer, updatePeers]);

  // Join voice room
  const joinVoice = useCallback(async () => {
    // 双重防护：防止快速点击或重复加入
    if (joiningRef.current || wsRef.current?.readyState === WebSocket.OPEN) return;
    joiningRef.current = true;
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          deviceId: selectedDevice ? { exact: selectedDevice } : undefined,
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
        },
      });
      localStreamRef.current = stream;
      connectSignaling();
      setJoined(true);
    } catch (err) {
      joiningRef.current = false;
      console.error("Voice join failed:", err);
      alert("无法访问麦克风: " + err);
    }
  }, [selectedDevice, connectSignaling]);

  // Toggle mute
  const toggleMute = useCallback(() => {
    if (localStreamRef.current) {
      const tracks = localStreamRef.current.getAudioTracks();
      const newMuted = !muted;
      tracks.forEach(t => (t.enabled = !newMuted));
      setMuted(newMuted);
      wsRef.current?.send(JSON.stringify({
        type: newMuted ? "webrtc_mute" : "webrtc_unmute",
      }));
    }
  }, [muted]);

  // KP：全员静音/取消全员静音
  const toggleMuteAll = useCallback(() => {
    const newAllMuted = !allMuted;
    setAllMuted(newAllMuted);
    // 广播 force_mute 给所有成员
    peersRef.current.forEach(p => {
      wsRef.current?.send(JSON.stringify({
        type: "webrtc_force_mute",
        target: p.memberId,
        muted: newAllMuted,
      }));
    });
    // 同步自己的静音状态
    if (localStreamRef.current) {
      localStreamRef.current.getAudioTracks().forEach(t => (t.enabled = !newAllMuted));
      setMuted(newAllMuted);
    }
  }, [allMuted]);

  // KP：强制静音某个成员
  const forceMutePeer = useCallback((peerId: string) => {
    const peer = peersRef.current.find(p => p.memberId === peerId);
    const newMuted = !peer?.muted;
    wsRef.current?.send(JSON.stringify({
      type: "webrtc_force_mute",
      target: peerId,
      muted: newMuted,
    }));
  }, []);

  // KP：踢出语音
  const kickPeer = useCallback((peerId: string) => {
    wsRef.current?.send(JSON.stringify({
      type: "webrtc_kick",
      target: peerId,
    }));
  }, []);

  // Leave voice
  const leaveVoice = useCallback(() => {
    // 清理重连定时器
    if (reconnectTimerRef.current) clearTimeout(reconnectTimerRef.current);
    localStreamRef.current?.getTracks().forEach(t => t.stop());
    localStreamRef.current = null;
    peersRef.current.forEach(p => {
      p.connection.close();
      abortControllersRef.current.get(p.memberId)?.abort();
    });
    abortControllersRef.current.clear();
    updatePeers(() => []);
    wsRef.current?.close();
    setJoined(false);
    joiningRef.current = false;
  }, [updatePeers]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (reconnectTimerRef.current) clearTimeout(reconnectTimerRef.current);
      localStreamRef.current?.getTracks().forEach(t => t.stop());
      peersRef.current.forEach(p => {
        p.connection.close();
        abortControllersRef.current.get(p.memberId)?.abort();
      });
      abortControllersRef.current.clear();
      wsRef.current?.close();
    };
  }, []);

  if (!joined) {
    return (
      <div className="voice-room">
        {/* 麦克风设备选择 */}
        {audioDevices.length > 1 && (
          <select
            className="voice-room__device"
            value={selectedDevice}
            onChange={e => setSelectedDevice(e.target.value)}
          >
            <option value="">默认麦克风</option>
            {audioDevices.map(d => (
              <option key={d.deviceId} value={d.deviceId}>{d.label || "未知设备"}</option>
            ))}
          </select>
        )}
        <button className="button button--ghost" onClick={joinVoice} type="button">
          加入语音房间
        </button>
        <span className="voice-room__hint">加入后可与其他在线成员实时语音通话</span>
      </div>
    );
  }

  return (
    <div className="voice-room voice-room--active">
      <div className="voice-room__header">
        <span className="voice-room__indicator" />
        <span>语音通话中</span>
        <span className="voice-room__count">{peers.length + 1} 人在线</span>
      </div>

      <div className="voice-room__members">
        <div className={"voice-peer" + (muted ? " voice-peer--muted" : " voice-peer--speaking")}>
          <span className="voice-peer__name">{memberName}（我）</span>
          <span className="voice-peer__status">{muted ? "已静音" : "发言中"}</span>
        </div>
        {peers.map(peer => (
          <div key={peer.memberId} className={"voice-peer" + (peer.muted ? " voice-peer--muted" : " voice-peer--speaking")}>
            <span className="voice-peer__name">{peer.displayName}</span>
            <span className="voice-peer__status">{peer.muted ? "已静音" : "在线"}</span>
            {/* KP 管理按钮 */}
            {isKeeper && (
              <div className="voice-peer__kp-actions">
                <button
                  className="voice-peer__kp-btn"
                  onClick={() => forceMutePeer(peer.memberId)}
                  type="button"
                  title={peer.muted ? "取消强制静音" : "强制静音"}
                >
                  {peer.muted ? "🔊" : "🔇"}
                </button>
                <button
                  className="voice-peer__kp-btn voice-peer__kp-btn--kick"
                  onClick={() => kickPeer(peer.memberId)}
                  type="button"
                  title="踢出语音"
                >
                  ✕
                </button>
              </div>
            )}
            {peer.stream && (
              <audio
                ref={(el) => {
                  if (el && peer.stream && el.srcObject !== peer.stream) {
                    el.srcObject = peer.stream;
                    el.play().catch(() => {});
                  }
                }}
                autoPlay
                playsInline
              />
            )}
          </div>
        ))}
      </div>

      <div className="voice-room__controls">
        {isKeeper && (
          <button
            className={`button ${allMuted ? "button--danger" : "button--ghost"}`}
            onClick={toggleMuteAll}
            type="button"
          >
            {allMuted ? "取消全员静音" : "全员静音"}
          </button>
        )}
        <button className={muted ? "button button--danger" : "button button--ghost"} onClick={toggleMute} type="button">
          {muted ? "取消静音" : "静音"}
        </button>
        <button className="button button--danger" onClick={leaveVoice} type="button">
          离开语音
        </button>
      </div>
    </div>
  );
}
