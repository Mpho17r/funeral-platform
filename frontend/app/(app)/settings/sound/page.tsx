"use client";

import { useState } from "react";
import { ArrowLeft, Play, Volume2 } from "lucide-react";
import { useRouter } from "next/navigation";

import {
  ALERT_TONES,
  RING_TONES,
  TONES,
  loadPrefs,
  previewTone,
  savePrefs,
  type SoundPrefs,
} from "@/lib/sound";

function ToneList({
  title,
  names,
  value,
  volume,
  onPick,
}: {
  title: string;
  names: string[];
  value: string;
  volume: number;
  onPick: (name: string) => void;
}) {
  return (
    <section className="rounded-2xl border bg-white p-5">
      <h2 className="font-semibold text-slate-900">{title}</h2>
      <ul className="mt-3 space-y-2">
        {names.map((n) => (
          <li key={n} className="flex items-center justify-between gap-3 rounded-lg border px-3 py-2">
            <label className="flex flex-1 cursor-pointer items-center gap-2 text-sm">
              <input type="radio" name={title} checked={value === n} onChange={() => onPick(n)} />
              {TONES[n].label}
            </label>
            <button
              type="button"
              onClick={() => previewTone(n, volume)}
              className="flex items-center gap-1 rounded-lg border px-2.5 py-1 text-xs text-slate-700 hover:bg-slate-50"
            >
              <Play size={12} /> Preview
            </button>
          </li>
        ))}
      </ul>
    </section>
  );
}

export default function SoundSettingsPage() {
  const router = useRouter();
  const [prefs, setPrefs] = useState<SoundPrefs>(() =>
    typeof window === "undefined" ? { enabled: true, tone: "chime", ring: "ring", volume: 0.6 } : loadPrefs(),
  );

  function change(next: Partial<SoundPrefs>) {
    const merged = { ...prefs, ...next };
    setPrefs(merged);
    savePrefs(merged);
  }

  return (
    <main className="mx-auto max-w-2xl space-y-5 p-4 sm:p-6">
      <button type="button" onClick={() => router.push("/settings")} className="flex items-center gap-2 text-sm text-slate-600 hover:text-slate-900">
        <ArrowLeft size={16} /> Back to Settings
      </button>
      <header className="flex items-center gap-3">
        <div className="rounded-xl bg-slate-900 p-3 text-white">
          <Volume2 size={20} />
        </div>
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Sounds and calls</h1>
          <p className="text-sm text-slate-500">
            Choose the tone for task and message alerts and the ring for voice calls. These choices are for you only, on this device.
          </p>
        </div>
      </header>

      <section className="space-y-4 rounded-2xl border bg-white p-5">
        <label className="flex items-center justify-between gap-3 text-sm font-medium text-slate-900">
          Play sounds
          <input type="checkbox" checked={prefs.enabled} onChange={(e) => change({ enabled: e.target.checked })} className="h-5 w-5" />
        </label>
        <label className="block text-sm font-medium text-slate-900">
          Volume
          <input
            type="range"
            min={0}
            max={1}
            step={0.05}
            value={prefs.volume}
            onChange={(e) => change({ volume: Number(e.target.value) })}
            className="mt-2 w-full"
          />
        </label>
      </section>

      <ToneList title="Alert tone (tasks, messages, reminders)" names={ALERT_TONES} value={prefs.tone} volume={prefs.volume} onPick={(tone) => change({ tone })} />
      <ToneList title="Voice call ring" names={RING_TONES} value={prefs.ring} volume={prefs.volume} onPick={(ring) => change({ ring })} />

      <p className="text-xs text-slate-500">
        Voice calls: open a colleague in Team chat, or press the phone button next to their name on your workstation. The call opens with the camera off.
      </p>
    </main>
  );
}
