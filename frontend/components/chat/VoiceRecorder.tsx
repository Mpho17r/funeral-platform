"use client";

import { useEffect, useRef, useState } from "react";
import { Loader2, Mic, SendHorizontal, Trash2 } from "lucide-react";

const MAX_SECONDS = 300;

function pickType(): string {
  const options = ["audio/webm;codecs=opus", "audio/webm", "audio/mp4", "audio/ogg"];
  for (const type of options) {
    if (typeof MediaRecorder !== "undefined" && MediaRecorder.isTypeSupported(type)) {
      return type;
    }
  }
  return "";
}

function clock(seconds: number) {
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return `${m}:${String(s).padStart(2, "0")}`;
}

/** Record a voice note when typing is not convenient. The recording is
 *  handed back as a file; the chat uploads and sends it. */
export function VoiceRecorder({
  disabled,
  onRecorded,
  onError,
  onActive,
}: {
  disabled?: boolean;
  onRecorded: (file: File) => Promise<void>;
  onError: (message: string) => void;
  onActive?: (active: boolean) => void;
}) {
  const [recording, setRecording] = useState(false);
  const [sending, setSending] = useState(false);
  const [seconds, setSeconds] = useState(0);
  const recorder = useRef<MediaRecorder | null>(null);
  const stream = useRef<MediaStream | null>(null);
  const chunks = useRef<Blob[]>([]);
  const timer = useRef<number | null>(null);
  const keep = useRef(true);

  function release() {
    if (timer.current) window.clearInterval(timer.current);
    timer.current = null;
    stream.current?.getTracks().forEach((t) => t.stop());
    stream.current = null;
    recorder.current = null;
    setRecording(false);
    setSeconds(0);
  }

  useEffect(() => {
    onActive?.(recording);
  }, [recording, onActive]);

  useEffect(() => {
    return () => {
      keep.current = false;
      if (recorder.current && recorder.current.state !== "inactive") {
        recorder.current.stop();
      }
      stream.current?.getTracks().forEach((t) => t.stop());
      if (timer.current) window.clearInterval(timer.current);
    };
  }, []);

  async function start() {
    if (typeof MediaRecorder === "undefined" || !navigator.mediaDevices) {
      onError("This browser cannot record voice notes.");
      return;
    }
    try {
      const media = await navigator.mediaDevices.getUserMedia({ audio: true });
      stream.current = media;
      chunks.current = [];
      keep.current = true;
      const type = pickType();
      const rec = new MediaRecorder(media, type ? { mimeType: type } : undefined);
      recorder.current = rec;
      rec.ondataavailable = (e) => {
        if (e.data.size > 0) chunks.current.push(e.data);
      };
      rec.onstop = async () => {
        const mime = rec.mimeType || type || "audio/webm";
        const parts = chunks.current;
        const send = keep.current;
        release();
        if (!send || parts.length === 0) return;
        const ext = mime.includes("mp4") ? "m4a" : mime.includes("ogg") ? "ogg" : "webm";
        const file = new File(parts, `voice-note.${ext}`, { type: mime });
        setSending(true);
        try {
          await onRecorded(file);
        } finally {
          setSending(false);
        }
      };
      rec.start();
      setRecording(true);
      setSeconds(0);
      timer.current = window.setInterval(() => {
        setSeconds((s) => {
          if (s + 1 >= MAX_SECONDS && recorder.current?.state === "recording") {
            recorder.current.stop();
          }
          return s + 1;
        });
      }, 1000);
    } catch {
      release();
      onError("Allow the microphone in your browser to record a voice note.");
    }
  }

  function finish(send: boolean) {
    keep.current = send;
    if (recorder.current && recorder.current.state !== "inactive") {
      recorder.current.stop();
    } else {
      release();
    }
  }

  if (recording) {
    return (
      <div className="flex min-h-[44px] flex-1 items-center gap-3 rounded-xl border border-red-300 bg-red-50 px-3 text-sm text-red-700">
        <span className="h-2.5 w-2.5 animate-pulse rounded-full bg-red-600" />
        <span className="font-medium tabular-nums">Recording {clock(seconds)}</span>
        <span className="flex-1" />
        <button
          type="button"
          onClick={() => finish(false)}
          aria-label="Discard the voice note"
          className="rounded-lg p-2 hover:bg-red-100"
        >
          <Trash2 size={18} />
        </button>
        <button
          type="button"
          onClick={() => finish(true)}
          aria-label="Send the voice note"
          className="flex items-center gap-1 rounded-lg bg-red-600 px-3 py-2 text-white"
        >
          <SendHorizontal size={16} /> Send
        </button>
      </div>
    );
  }

  return (
    <button
      type="button"
      onClick={() => void start()}
      disabled={disabled || sending}
      aria-label="Record a voice note"
      title="Record a voice note"
      className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl text-[var(--fos-text-secondary)] hover:bg-[var(--fos-surface-muted)] disabled:opacity-40"
    >
      {sending ? <Loader2 size={18} className="animate-spin" /> : <Mic size={18} />}
    </button>
  );
}
