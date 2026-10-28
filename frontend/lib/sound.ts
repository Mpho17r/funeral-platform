/** Sounds for alerts and calls. Tones are made in the browser, so there
 * are no files to load. Each person's choices live in their own browser. */

export type SoundPrefs = {
  enabled: boolean;
  /** Tone for tasks, messages and other alerts. */
  tone: string;
  /** Tone repeated for incoming calls. */
  ring: string;
  volume: number; // 0 to 1
};

type Note = { f: number; t: number; d: number };

export const TONES: Record<string, { label: string; notes: Note[] }> = {
  chime: { label: "Chime", notes: [{ f: 880, t: 0, d: 0.18 }, { f: 1175, t: 0.16, d: 0.3 }] },
  bell: { label: "Bell", notes: [{ f: 1318, t: 0, d: 0.5 }, { f: 988, t: 0.05, d: 0.6 }] },
  pop: { label: "Soft pop", notes: [{ f: 520, t: 0, d: 0.1 }] },
  rise: { label: "Rising", notes: [{ f: 523, t: 0, d: 0.12 }, { f: 659, t: 0.12, d: 0.12 }, { f: 784, t: 0.24, d: 0.2 }] },
  calm: { label: "Calm", notes: [{ f: 440, t: 0, d: 0.35 }, { f: 349, t: 0.3, d: 0.5 }] },
  ring: { label: "Classic ring", notes: [{ f: 700, t: 0, d: 0.35 }, { f: 900, t: 0.4, d: 0.35 }, { f: 700, t: 0.9, d: 0.35 }, { f: 900, t: 1.3, d: 0.35 }] },
  gentle: { label: "Gentle ring", notes: [{ f: 523, t: 0, d: 0.4 }, { f: 659, t: 0.45, d: 0.4 }, { f: 784, t: 0.9, d: 0.6 }] },
};

export const ALERT_TONES = ["chime", "bell", "pop", "rise", "calm"];
export const RING_TONES = ["ring", "gentle", "bell"];

export const DEFAULTS: SoundPrefs = { enabled: true, tone: "chime", ring: "ring", volume: 0.6 };

const KEY = "fos.sound";

export function loadPrefs(): SoundPrefs {
  try {
    const raw = window.localStorage.getItem(KEY);
    if (!raw) return DEFAULTS;
    const p = JSON.parse(raw) as Partial<SoundPrefs>;
    return {
      enabled: p.enabled !== false,
      tone: p.tone && TONES[p.tone] ? p.tone : DEFAULTS.tone,
      ring: p.ring && TONES[p.ring] ? p.ring : DEFAULTS.ring,
      volume: typeof p.volume === "number" ? Math.min(1, Math.max(0, p.volume)) : DEFAULTS.volume,
    };
  } catch {
    return DEFAULTS;
  }
}

export function savePrefs(prefs: SoundPrefs) {
  try {
    window.localStorage.setItem(KEY, JSON.stringify(prefs));
  } catch {
    /* storage blocked: the choice lasts until the page closes */
  }
}

let context: AudioContext | null = null;

function play(name: string, volume: number) {
  const tone = TONES[name];
  if (!tone || volume <= 0) return;
  try {
    const Ctx =
      window.AudioContext ??
      (window as unknown as { webkitAudioContext?: typeof AudioContext }).webkitAudioContext;
    if (!Ctx) return;
    context = context ?? new Ctx();
    if (context.state === "suspended") void context.resume();
    const start = context.currentTime + 0.02;
    for (const n of tone.notes) {
      const osc = context.createOscillator();
      const gain = context.createGain();
      osc.type = "sine";
      osc.frequency.value = n.f;
      gain.gain.setValueAtTime(0.0001, start + n.t);
      gain.gain.exponentialRampToValueAtTime(Math.max(0.0002, volume * 0.5), start + n.t + 0.02);
      gain.gain.exponentialRampToValueAtTime(0.0001, start + n.t + n.d);
      osc.connect(gain).connect(context.destination);
      osc.start(start + n.t);
      osc.stop(start + n.t + n.d + 0.05);
    }
  } catch {
    /* the browser blocked sound until the person clicks: ignore */
  }
}

/** Play the person's chosen tone. `call` uses the ring tone. */
export function playTone(kind: "task" | "message" | "call" | "alert") {
  const prefs = loadPrefs();
  if (!prefs.enabled) return;
  play(kind === "call" ? prefs.ring : prefs.tone, prefs.volume);
}

/** For the Preview buttons on the settings page (ignores "sound off"). */
export function previewTone(name: string, volume: number) {
  play(name, volume);
}
