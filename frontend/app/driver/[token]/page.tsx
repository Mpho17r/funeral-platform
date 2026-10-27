"use client";

import { useCallback, useEffect, useState } from "react";
import { useParams } from "next/navigation";
import axios from "axios";
import { Car, Loader2 } from "lucide-react";

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";

type Job = {
  id: string;
  status: string;
  label: string;
  report_time: string;
  deceased_full_name: string | null;
  pickup_address: string | null;
  venue: string | null;
  destination: string | null;
  dress_code: string | null;
  instructions: string | null;
  pay_amount: string;
  car: string | null;
};

export default function DriverPage() {
  const { token } = useParams<{ token: string }>();
  const [name, setName] = useState("");
  const [jobs, setJobs] = useState<Job[] | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState("");

  const load = useCallback(async () => {
    try {
      const r = await axios.get(`${API}/driver-portal/${token}`);
      setName(r.data.driver);
      setJobs(r.data.jobs);
      setError("");
    } catch (e) {
      setError(
        axios.isAxiosError(e) && e.response?.status === 429
          ? "Too many attempts. Please try again in a few minutes."
          : "This link is not valid any more. Please ask the funeral home for a new one."
      );
    }
  }, [token]);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    load();
  }, [load]);

  async function respond(id: string, accept: boolean) {
    setBusy(id);
    try {
      await axios.post(`${API}/driver-portal/${token}/jobs/${id}/respond`, { accept });
      await load();
    } catch {
      setError("Could not save your answer. Please try again.");
    } finally {
      setBusy("");
    }
  }

  return (
    <main className="min-h-screen bg-slate-50 px-4 py-8">
      <div className="mx-auto max-w-xl space-y-4">
        {!jobs && !error && (
          <p className="flex items-center gap-2 text-slate-500">
            <Loader2 className="animate-spin" size={18} /> Loading…
          </p>
        )}
        {error && <p className="rounded-xl border bg-white p-5 text-slate-700">{error}</p>}

        {jobs && (
          <>
            <header className="flex items-center gap-3">
              <div className="rounded-xl bg-slate-900 p-3 text-white"><Car size={22} /></div>
              <div>
                <h1 className="text-xl font-bold text-slate-900">Hello {name.split(" ")[0]}</h1>
                <p className="text-sm text-slate-500">Your funeral car jobs</p>
              </div>
            </header>

            {jobs.length === 0 && (
              <p className="rounded-xl border bg-white p-5 text-slate-600">
                You have no jobs right now. We will message you when there is one.
              </p>
            )}

            {jobs.map((j) => (
              <section key={j.id} className="space-y-3 rounded-2xl border border-slate-200 bg-white p-5">
                <div className="flex items-center justify-between">
                  <h2 className="font-semibold text-slate-900">{j.label}</h2>
                  <span className={`rounded-full px-3 py-1 text-xs font-medium ${j.status === "accepted" ? "bg-emerald-50 text-emerald-700" : "bg-amber-50 text-amber-700"}`}>
                    {j.status === "accepted" ? "You accepted" : "Waiting for your answer"}
                  </span>
                </div>
                <dl className="grid grid-cols-[7rem_1fr] gap-y-1.5 text-sm">
                  <dt className="text-slate-500">Report at</dt>
                  <dd className="font-medium">{new Date(j.report_time).toLocaleString("en-ZA", { dateStyle: "full", timeStyle: "short" })}</dd>
                  {j.deceased_full_name && (<><dt className="text-slate-500">Funeral of</dt><dd>{j.deceased_full_name}</dd></>)}
                  {j.pickup_address && (<><dt className="text-slate-500">Pick up</dt><dd>{j.pickup_address}</dd></>)}
                  {j.venue && (<><dt className="text-slate-500">Venue</dt><dd>{j.venue}</dd></>)}
                  {j.destination && (<><dt className="text-slate-500">Then to</dt><dd>{j.destination}</dd></>)}
                  {j.dress_code && (<><dt className="text-slate-500">Dress code</dt><dd>{j.dress_code}</dd></>)}
                  {j.car && (<><dt className="text-slate-500">Your car</dt><dd className="capitalize">{j.car}</dd></>)}
                  {Number(j.pay_amount) > 0 && (<><dt className="text-slate-500">Pay</dt><dd>R {Number(j.pay_amount).toFixed(2)}</dd></>)}
                  {j.instructions && (<><dt className="text-slate-500">Notes</dt><dd>{j.instructions}</dd></>)}
                </dl>
                <div className="flex gap-3">
                  {j.status !== "accepted" && (
                    <button disabled={busy === j.id} onClick={() => respond(j.id, true)} className="flex-1 rounded-lg bg-slate-900 px-4 py-3 text-sm font-semibold text-white disabled:opacity-50">
                      Accept
                    </button>
                  )}
                  <button disabled={busy === j.id} onClick={() => respond(j.id, false)} className="flex-1 rounded-lg border border-slate-300 px-4 py-3 text-sm font-medium text-slate-700 disabled:opacity-50">
                    {j.status === "accepted" ? "I can no longer do it" : "Decline"}
                  </button>
                </div>
              </section>
            ))}
          </>
        )}
      </div>
    </main>
  );
}
