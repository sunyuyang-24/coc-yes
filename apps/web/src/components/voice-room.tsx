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
};

export function VoiceRoom({ roomId, memberId, memberName }: Props) {
  const [joined, setJoined] = useState(false);
  const [peers, setPeers] = useState<VoicePeer[]>([]);
  const [muted, setMuted] = useState(false);
  const localStreamRef = useRef<MediaStream | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const peersRef = useRef<VoicePeer[]>([]);

  const updatePeers = useCallback((updater: (prev: VoicePeer[]) => VoicePeer[]) => {
    setPeers(prev => {
      const next = updater(prev);
      peersRef.current = next;
      return next;
    });
  }, []);

  // Create peer connection
  const createPeer = useCallback((targetId: string, displayName: string, isPolite: boolean) => {
    const pc = new RTCPeerConnection({
      iceServers: [{ urls: "stun:stun.l.google.com:19302" }],
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

    // Track connection state
    pc.onconnectionstatechange = () => {
      if (pc.connectionState === "failed" || pc.connectionState === "disconnected") {
        updatePeers(prev => prev.filter(p => p.memberId !== targetId));
        pc.close();
      }
    };

    return pc;
  }, [updatePeers]);

  // Join voice room
  const joinVoice = useCallback(async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
        },
      });
      localStreamRef.current = stream;

      // Connect signaling WebSocket
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
            const fromName = "成员";
            const pc = createPeer(fromId, fromName, polite);
            updatePeers(prev => {
              if (prev.find(p => p.memberId === fromId)) return prev;
              return [...prev, { memberId: fromId, displayName: fromName, connection: pc, muted: false }];
            });
            break;
          }
          case "webrtc_voice_leave": {
            const peer = peersRef.current.find(p => p.memberId === fromId);
            peer?.connection.close();
            updatePeers(prev => prev.filter(p => p.memberId !== fromId));
            break;
          }
          case "webrtc_offer": {
            const existing = peersRef.current.find(p => p.memberId === fromId);
            if (existing) {
              existing.connection.setRemoteDescription(new RTCSessionDescription(msg.sdp))
                .then(() => existing.connection.createAnswer())
                .then(answer => {
                  existing.connection.setLocalDescription(answer);
                  ws.send(JSON.stringify({
                    type: "webrtc_answer",
                    target: fromId,
                    sdp: answer,
                  }));
                }).catch(console.error);
            }
            break;
          }
          case "webrtc_answer": {
            const peer = peersRef.current.find(p => p.memberId === fromId);
            peer?.connection.setRemoteDescription(new RTCSessionDescription(msg.sdp))
              .catch(console.error);
            break;
          }
          case "webrtc_ice": {
            const peer = peersRef.current.find(p => p.memberId === fromId);
            if (msg.candidate && peer) {
              peer.connection.addIceCandidate(new RTCIceCandidate(msg.candidate))
                .catch(console.error);
            }
            break;
          }
          case "webrtc_mute":
          case "webrtc_unmute": {
            updatePeers(prev =>
              prev.map(p => p.memberId === fromId ? { ...p, muted: msg.type === "webrtc_mute" } : p)
            );
            break;
          }
        }
      };

      ws.onclose = () => {
        // Cleanup all peers
        peersRef.current.forEach(p => p.connection.close());
        updatePeers(() => []);
        setJoined(false);
      };

      setJoined(true);
    } catch (err) {
      console.error("Voice join failed:", err);
      alert("无法访问麦克风: " + err);
    }
  }, [roomId, memberId, createPeer, updatePeers]);

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

  // Leave voice
  const leaveVoice = useCallback(() => {
    localStreamRef.current?.getTracks().forEach(t => t.stop());
    localStreamRef.current = null;
    peersRef.current.forEach(p => p.connection.close());
    updatePeers(() => []);
    wsRef.current?.close();
    setJoined(false);
  }, [updatePeers]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      localStreamRef.current?.getTracks().forEach(t => t.stop());
      peersRef.current.forEach(p => p.connection.close());
      wsRef.current?.close();
    };
  }, []);

  if (!joined) {
    return (
      <div className="voice-room">
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
          <div key={peer.memberId} className={"voice-peer" + (muted ? " voice-peer--muted" : " voice-peer--speaking")}>
            <span className="voice-peer__name">{peer.displayName}</span>
            <span className="voice-peer__status">{peer.muted ? "已静音" : "在线"}</span>
            {peer.stream && (
              <audio
                ref={(el) => { if (el) el.srcObject = peer.stream!; }}
                autoPlay
                playsInline
              />
            )}
          </div>
        ))}
      </div>

      <div className="voice-room__controls">
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
