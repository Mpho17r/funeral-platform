"use client";

import { FormEvent, useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { Loader2, Send, Sparkles, Trash2 } from "lucide-react";

import api from "@/lib/api";
import { getApiErrorMessage } from "@/lib/format";
import { ErrorNote } from "@/components/Notices";

type Item = { label: string; href: string };
type Pending = { id: string; summary: string };
type Line = {
  speaker: "user" | "kai";
  text: string;
  items?: Item[];
  action?: Pending | null;
  settled?: string;
};
type Hello = {
  reply: string;
  branch: string | null;
  briefing: { key: string; text: string; items: Item[] }[];
  suggestions: string[];
};

export default function KaiPage() {
  const [lines, setLines] = useState<Line[]>([]);
  const [suggestions, setSuggestions] = useState<string[]>([]);
  const [branch, setBranch] = useState<string | null>(null);
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const end = useRef<HTMLDivElement>(null);

  const start = useCallback(() => {
    setError("");
    return Promise.all([
      api.get<{ speaker: "user" | "kai"; text: string; items?: Item[] }[]>(
        "/kai/history",
      ),
      api.get<Hello>("/kai/hello"),
    ])
      .then(([past, hi]) => {
        const earlier: Line[] = past.data.map((p) => ({
          speaker: p.speaker,
          text: p.text,
          items: p.items ?? [],
        }));
        // hello() is also saved to history, so show the earlier talk
        // first, then the fresh greeting with its list of cases.
        const items = hi.data.briefing.flatMap((b) => b.items);
        setLines([...earlier.slice(0, -1), { speaker: "kai", text: hi.data.reply, items }]);
        setSuggestions(hi.data.suggestions);
        setBranch(hi.data.branch);
      })
      .catch((err) => setError(getApiErrorMessage(err, "KAI could not start.")));
  }, []);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void start();
  }, [start]);

  useEffect(() => {
    end.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [lines, busy]);

  async function say(value: string) {
    const message = value.trim();
    if (message.length < 1 || busy) return;
    setText("");
    setError("");
    setLines((l) => [...l, { speaker: "user", text: message }]);
    try {
      setBusy(true);
      const r = await api.post<{
        reply: string;
        items: Item[];
        action?: Pending | null;
        suggestions?: string[];
      }>("/kai/message", { text: message });
      setLines((l) => [
        ...l,
        { speaker: "kai", text: r.data.reply, items: r.data.items, action: r.data.action },
      ]);
      if (r.data.suggestions?.length) setSuggestions(r.data.suggestions);
    } catch (err) {
      setError(getApiErrorMessage(err, "KAI could not answer just now."));
    } finally {
      setBusy(false);
    }
  }

  async function decide(index: number, id: string, choice: "confirm" | "cancel") {
    try {
      setBusy(true);
      const r = await api.post<{ ok: boolean; reply: string; items?: Item[] }>(
        `/kai/actions/${id}/${choice}`,
      );
      setLines((l) =>
        l.map((line, i) =>
          i === index ? { ...line, action: null, settled: choice } : line,
        ),
      );
      setLines((l) => [
        ...l,
        { speaker: "kai", text: r.data.reply, items: r.data.items ?? [] },
      ]);
    } catch (err) {
      setError(getApiErrorMessage(err, "That did not go through."));
    } finally {
      setBusy(false);
    }
  }

  async function clear() {
    try {
      await api.delete("/kai/history");
      await start();
    } catch (err) {
      setError(getApiErrorMessage(err, "Could not clear the conversation."));
    }
  }

  function submit(e: FormEvent) {
    e.preventDefault();
    void say(text);
  }

  return (
    <main className="mx-auto flex max-w-2xl flex-col gap-4 p-4 sm:p-6">
      <header className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <div className="rounded-xl bg-slate-900 p-3 text-white">
            <Sparkles size={20} />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-slate-900">KAI</h1>
            <p className="text-sm text-slate-500">
              Knowledge · Assistance · Intelligence
              {branch ? ` — ${branch}` : ""}
            </p>
          </div>
        </div>
        <button
          type="button"
          onClick={() => void clear()}
          className="flex items-center gap-1 rounded-lg border px-3 py-2 text-xs text-slate-600 hover:bg-slate-50"
          title="Clear this conversation"
        >
          <Trash2 size={14} /> Clear
        </button>
      </header>

      {error && <ErrorNote message={error} />}

      <section className="space-y-3" aria-live="polite">
        {lines.map((line, i) => (
          <div
            key={i}
            className={line.speaker === "user" ? "flex justify-end" : "flex justify-start"}
          >
            <div
              className={
                line.speaker === "user"
                  ? "max-w-[85%] rounded-2xl rounded-br-sm bg-slate-900 px-4 py-2.5 text-sm text-white"
                  : "max-w-[92%] rounded-2xl rounded-bl-sm border bg-white px-4 py-3 text-sm text-slate-800"
              }
            >
              <p className="whitespace-pre-wrap">{line.text}</p>
              {line.items && line.items.length > 0 && (
                <ul className="mt-2 divide-y border-t">
                  {line.items.map((item, j) => (
                    <li key={j} className="py-1.5">
                      <Link href={item.href} className="text-slate-800 hover:underline">
                        {item.label}
                      </Link>
                    </li>
                  ))}
                </ul>
              )}
              {line.action && (
                <div className="mt-3 rounded-xl bg-slate-50 p-3">
                  <p className="text-xs font-semibold text-slate-600">Waiting for you</p>
                  <p className="mt-1 text-sm">{line.action.summary}</p>
                  <div className="mt-2 flex gap-2">
                    <button
                      type="button"
                      disabled={busy}
                      onClick={() => void decide(i, line.action!.id, "confirm")}
                      className="rounded-lg bg-slate-900 px-3 py-1.5 text-xs font-medium text-white disabled:opacity-60"
                    >
                      Yes, do it
                    </button>
                    <button
                      type="button"
                      disabled={busy}
                      onClick={() => void decide(i, line.action!.id, "cancel")}
                      className="rounded-lg border px-3 py-1.5 text-xs text-slate-700 disabled:opacity-60"
                    >
                      Leave it
                    </button>
                  </div>
                </div>
              )}
            </div>
          </div>
        ))}
        {busy && (
          <div className="flex items-center gap-2 text-sm text-slate-500">
            <Loader2 size={16} className="animate-spin" /> KAI is checking the records…
          </div>
        )}
        <div ref={end} />
      </section>

      {suggestions.length > 0 && (
        <div className="flex flex-wrap gap-2">
          {suggestions.map((s) => (
            <button
              key={s}
              type="button"
              onClick={() => void say(s)}
              className="rounded-full border border-slate-300 bg-white px-3 py-1.5 text-sm text-slate-700 hover:bg-slate-50"
            >
              {s}
            </button>
          ))}
        </div>
      )}

      <form onSubmit={submit} className="sticky bottom-0 flex gap-2 bg-slate-50 pb-2 pt-1">
        <input
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder="Ask KAI anything about your work…"
          maxLength={500}
          className="w-full rounded-lg border border-slate-300 px-4 py-3 text-sm outline-none focus:border-slate-900"
        />
        <button
          type="submit"
          disabled={busy}
          aria-label="Send"
          className="flex items-center rounded-lg bg-slate-900 px-4 text-white disabled:opacity-60"
        >
          <Send size={18} />
        </button>
      </form>
    </main>
  );
}
