"use client";

import { FormEvent, useEffect, useState } from "react";
import Link from "next/link";
import { Loader2, Send, Sparkles } from "lucide-react";

import api from "@/lib/api";
import { getApiErrorMessage } from "@/lib/format";
import { ErrorNote } from "@/components/Notices";

type Answer = {
  understood: boolean;
  answer: string;
  items: { label: string; href: string }[];
  suggestions: { key: string; example: string }[];
};

export default function AssistantPage() {
  const [question, setQuestion] = useState("");
  const [asked, setAsked] = useState("");
  const [result, setResult] = useState<Answer | null>(null);
  const [examples, setExamples] = useState<{ key: string; example: string }[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    api
      .get<{ key: string; example: string }[]>("/assistant/questions")
      .then((r) => setExamples(r.data))
      .catch(() => setExamples([]));
  }, []);

  async function ask(text: string) {
    if (text.trim().length < 2) return;
    try {
      setBusy(true);
      setError("");
      setAsked(text);
      const r = await api.post<Answer>("/assistant/ask", { question: text });
      setResult(r.data);
    } catch (err) {
      setError(getApiErrorMessage(err, "Could not get an answer."));
    } finally {
      setBusy(false);
    }
  }

  function submit(e: FormEvent) {
    e.preventDefault();
    void ask(question);
  }

  const chips = result && result.suggestions.length ? result.suggestions : examples;

  return (
    <main className="mx-auto max-w-2xl space-y-5 p-4 sm:p-6">
      <header className="flex items-center gap-3">
        <div className="rounded-xl bg-slate-900 p-3 text-white">
          <Sparkles size={20} />
        </div>
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Ask FuneralOS</h1>
          <p className="text-sm text-slate-500">
            Answers come from your real records, and only what you are allowed to see.
          </p>
        </div>
      </header>

      <form onSubmit={submit} className="flex gap-2">
        <input
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          placeholder="For example: which memberships are in arrears?"
          maxLength={300}
          className="w-full rounded-lg border border-slate-300 px-4 py-3 text-sm outline-none focus:border-slate-900"
        />
        <button
          type="submit"
          disabled={busy}
          aria-label="Ask"
          className="flex items-center rounded-lg bg-slate-900 px-4 text-white disabled:opacity-60"
        >
          {busy ? <Loader2 size={18} className="animate-spin" /> : <Send size={18} />}
        </button>
      </form>

      {error && <ErrorNote message={error} />}

      {result && (
        <section className="rounded-2xl border bg-white p-5">
          <p className="text-xs text-slate-500">{asked}</p>
          <p className="mt-1 text-base font-semibold text-slate-900">{result.answer}</p>
          {result.items.length > 0 && (
            <ul className="mt-3 divide-y text-sm">
              {result.items.map((item, i) => (
                <li key={i} className="py-2">
                  <Link href={item.href} className="text-slate-800 hover:underline">
                    {item.label}
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </section>
      )}

      {chips.length > 0 && (
        <div>
          <p className="mb-2 text-sm font-medium text-slate-700">You can ask</p>
          <div className="flex flex-wrap gap-2">
            {chips.map((c) => (
              <button
                key={c.key}
                type="button"
                onClick={() => {
                  setQuestion(c.example);
                  void ask(c.example);
                }}
                className="rounded-full border border-slate-300 bg-white px-3 py-1.5 text-sm text-slate-700 hover:bg-slate-50"
              >
                {c.example}
              </button>
            ))}
          </div>
        </div>
      )}
    </main>
  );
}
