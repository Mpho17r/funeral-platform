"use client";

import { FormEvent, Suspense, useCallback, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import { Car, Link2, Loader2, MessageCircle, Plus, Wand2 } from "lucide-react";

import { useCurrentUser } from "@/components/CurrentUserProvider";
import { Dialog, inputClass } from "@/components/Dialog";
import api from "@/lib/api";
import { formatMoney, getApiErrorMessage } from "@/lib/format";

type Vehicle = {
  id: string;
  make: string | null;
  model: string | null;
  vehicle_type: string;
  colour: string;
  registration: string | null;
  seats: number;
  is_active: boolean;
};
type Driver = {
  id: string;
  full_name: string;
  phone: string | null;
  email: string | null;
  area: string | null;
  is_active: boolean;
  has_link: boolean;
  vehicles: Vehicle[];
};
type Job = {
  id: string;
  case_id: string;
  case_number: string | null;
  deceased_full_name: string | null;
  label: string;
  required_colour: string | null;
  required_type: string | null;
  required_model: string | null;
  report_time: string;
  venue: string | null;
  destination: string | null;
  dress_code: string | null;
  pay_amount: string;
  status: string;
  driver_name: string | null;
  vehicle: string | null;
  alert_error: string | null;
  alerted_at: string | null;
  paid: boolean;
};
type Candidate = { driver_id: string; driver_name: string; vehicle: Vehicle };
type CaseRow = { id: string; case_number: string; deceased_full_name: string; funeral_date: string | null; funeral_venue?: string | null };

const TYPES = ["sedan", "suv", "minibus", "limousine", "hearse", "bakkie", "van", "other"];
const STATUS_STYLE: Record<string, string> = {
  open: "bg-red-50 text-red-700",
  assigned: "bg-amber-50 text-amber-700",
  accepted: "bg-emerald-50 text-emerald-700",
  completed: "bg-blue-50 text-blue-700",
  cancelled: "bg-slate-100 text-slate-500",
};

const when = (v: string) =>
  new Date(v).toLocaleString("en-ZA", { weekday: "short", day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit" });

export default function TransportPage() {
  return (
    <Suspense fallback={null}>
      <TransportScreen />
    </Suspense>
  );
}

function TransportScreen() {
  const { can } = useCurrentUser();
  const manage = can("transport.manage");
  const caseParam = useSearchParams().get("case");

  const [tab, setTab] = useState<"jobs" | "drivers">("jobs");
  const [jobs, setJobs] = useState<Job[]>([]);
  const [drivers, setDrivers] = useState<Driver[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [assigning, setAssigning] = useState<Job | null>(null);
  const [newJobs, setNewJobs] = useState(!!caseParam);
  const [driverDialog, setDriverDialog] = useState<Driver | "new" | null>(null);
  const [carFor, setCarFor] = useState<Driver | null>(null);
  const [day, setDay] = useState("");

  const load = useCallback(async () => {
    try {
      const [j, d] = await Promise.all([
        api.get<Job[]>("/transport/jobs", { params: { day: day || undefined, case_id: caseParam || undefined } }),
        api.get<Driver[]>("/transport/drivers", { params: { include_inactive: true } }),
      ]);
      setJobs(j.data);
      setDrivers(d.data);
      setError("");
    } catch (err) {
      setError(getApiErrorMessage(err, "Could not load drivers and jobs."));
    } finally {
      setLoading(false);
    }
  }, [day, caseParam]);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    load();
  }, [load]);

  async function autoAssign() {
    setError("");
    try {
      const r = await api.post("/transport/auto-assign", { day: day || undefined, case_id: caseParam || undefined });
      setNotice(`${r.data.assigned} job(s) assigned automatically. ${r.data.still_open} still need a driver.`);
      load();
    } catch (err) {
      setError(getApiErrorMessage(err, "Could not assign automatically."));
    }
  }

  async function action(job: Job, path: string) {
    setError("");
    try {
      await api.post(`/transport/jobs/${job.id}/${path}`);
      load();
    } catch (err) {
      setError(getApiErrorMessage(err, "That did not work."));
    }
  }

  async function whatsapp(job: Job) {
    try {
      const r = await api.get<{ whatsapp: string | null; text: string }>(`/transport/jobs/${job.id}/alert`);
      if (r.data.whatsapp) window.open(r.data.whatsapp, "_blank", "noopener");
      else {
        await navigator.clipboard?.writeText(r.data.text);
        setNotice("This driver has no phone number. The alert text was copied.");
      }
    } catch (err) {
      setError(getApiErrorMessage(err, "Could not prepare the alert."));
    }
  }

  async function makeLink(d: Driver) {
    try {
      const r = await api.post<{ path: string }>(`/transport/drivers/${d.id}/link`);
      const url = `${window.location.origin}${r.data.path}`;
      await navigator.clipboard?.writeText(url);
      setNotice(`Private link for ${d.full_name} copied. It is shown only now: ${url}`);
      load();
    } catch (err) {
      setError(getApiErrorMessage(err, "Could not make the link."));
    }
  }

  const open = jobs.filter((j) => j.status === "open").length;

  return (
    <main className="mx-auto max-w-6xl space-y-6 p-6 md:p-8">
      <header className="flex flex-wrap items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <div className="rounded-xl bg-slate-900 p-3 text-white"><Car size={22} /></div>
          <div>
            <h1 className="text-2xl font-bold text-[var(--fos-text)]">Partner drivers</h1>
            <p className="text-sm text-[var(--fos-text-muted)]">
              Drivers with their own cars, matched to funerals by colour and type.
            </p>
          </div>
        </div>
        {manage && (
          <div className="flex flex-wrap gap-3">
            <button onClick={() => setDriverDialog("new")} className="flex items-center gap-2 rounded-lg border border-slate-300 bg-white px-4 py-2.5 text-sm font-medium text-slate-700"><Plus size={16} /> Add driver</button>
            <button onClick={() => setNewJobs(true)} className="flex items-center gap-2 rounded-lg bg-slate-900 px-4 py-2.5 text-sm font-semibold text-white"><Plus size={16} /> Car jobs for a funeral</button>
          </div>
        )}
      </header>

      {error && <p role="alert" className="rounded-lg bg-red-50 p-3 text-sm text-red-700">{error}</p>}
      {notice && <p role="status" className="break-all rounded-lg bg-emerald-50 p-3 text-sm text-emerald-700">{notice}</p>}

      <div className="flex flex-wrap items-center gap-2">
        {(["jobs", "drivers"] as const).map((t) => (
          <button key={t} onClick={() => setTab(t)} className={`rounded-full px-4 py-2 text-sm font-medium ${tab === t ? "bg-slate-900 text-white" : "bg-white text-slate-600 border border-slate-200"}`}>
            {t === "jobs" ? `Car jobs${open ? ` (${open} open)` : ""}` : `Drivers (${drivers.filter((d) => d.is_active).length})`}
          </button>
        ))}
        {tab === "jobs" && (
          <>
            <input type="date" value={day} onChange={(e) => setDay(e.target.value)} className="ml-auto rounded-lg border border-slate-300 px-3 py-2 text-sm" aria-label="Filter by day" />
            {manage && open > 0 && (
              <button onClick={autoAssign} className="flex items-center gap-2 rounded-lg border border-emerald-300 bg-emerald-50 px-4 py-2 text-sm font-medium text-emerald-800"><Wand2 size={16} /> Match all open jobs</button>
            )}
          </>
        )}
      </div>

      {loading && <Loader2 className="animate-spin text-slate-400" />}

      {tab === "jobs" && (
        <div className="space-y-3">
          {jobs.length === 0 && !loading && <p className="text-sm text-[var(--fos-text-muted)]">No car jobs {day ? "on this day" : "yet"}.</p>}
          {jobs.map((j) => (
            <div key={j.id} className="rounded-xl border border-[var(--fos-border)] bg-[var(--fos-surface)] p-4">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <p className="font-medium text-[var(--fos-text)]">
                    {j.label} · {when(j.report_time)}
                  </p>
                  <p className="text-sm text-[var(--fos-text-muted)]">
                    {j.deceased_full_name} ({j.case_number}) · {[j.required_colour, j.required_type, j.required_model].filter(Boolean).join(" ") || "any car"}
                  </p>
                  <p className="text-sm text-[var(--fos-text-muted)]">{[j.venue, j.destination && `→ ${j.destination}`, j.dress_code && `Dress: ${j.dress_code}`].filter(Boolean).join(" · ")}</p>
                  {j.driver_name && <p className="mt-1 text-sm font-medium capitalize">{j.driver_name} · {j.vehicle}</p>}
                  {j.alert_error && j.status === "assigned" && <p className="text-xs text-amber-700">{j.alert_error}</p>}
                </div>
                <div className="flex flex-col items-end gap-2">
                  <span className={`rounded-full px-3 py-1 text-xs font-medium ${STATUS_STYLE[j.status]}`}>{j.status}</span>
                  {Number(j.pay_amount) > 0 && <span className="text-xs text-[var(--fos-text-muted)]">Pay R {formatMoney(j.pay_amount)}{j.paid ? " · paid" : ""}</span>}
                </div>
              </div>
              {manage && j.status !== "completed" && j.status !== "cancelled" && (
                <div className="mt-3 flex flex-wrap gap-2 text-sm">
                  {j.status === "open" && <button onClick={() => setAssigning(j)} className="rounded-lg bg-slate-900 px-3 py-1.5 font-medium text-white">Choose driver</button>}
                  {j.driver_name && <button onClick={() => whatsapp(j)} className="flex items-center gap-1 rounded-lg border border-slate-300 px-3 py-1.5"><MessageCircle size={14} /> WhatsApp alert</button>}
                  {j.driver_name && <button onClick={() => action(j, "resend")} className="rounded-lg border border-slate-300 px-3 py-1.5">Email again</button>}
                  {j.driver_name && <button onClick={() => action(j, "unassign")} className="rounded-lg border border-slate-300 px-3 py-1.5">Remove driver</button>}
                  {j.driver_name && <button onClick={() => action(j, "complete")} className="rounded-lg border border-emerald-300 px-3 py-1.5 text-emerald-800">Mark done</button>}
                  <button onClick={() => action(j, "cancel")} className="rounded-lg border border-red-200 px-3 py-1.5 text-red-700">Cancel</button>
                </div>
              )}
              {manage && j.status === "completed" && !j.paid && Number(j.pay_amount) > 0 && (
                <button onClick={() => action(j, "pay")} className="mt-3 rounded-lg bg-slate-900 px-3 py-1.5 text-sm font-medium text-white">Record payment to driver</button>
              )}
            </div>
          ))}
        </div>
      )}

      {tab === "drivers" && (
        <div className="grid gap-3 md:grid-cols-2">
          {drivers.length === 0 && !loading && <p className="text-sm text-[var(--fos-text-muted)]">No drivers yet. Add the people with cars who help on funeral days.</p>}
          {drivers.map((d) => (
            <div key={d.id} className={`rounded-xl border border-[var(--fos-border)] bg-[var(--fos-surface)] p-4 ${d.is_active ? "" : "opacity-50"}`}>
              <div className="flex items-start justify-between gap-3">
                <div>
                  <p className="font-medium text-[var(--fos-text)]">{d.full_name}</p>
                  <p className="text-sm text-[var(--fos-text-muted)]">{[d.phone, d.email, d.area].filter(Boolean).join(" · ")}</p>
                </div>
                {manage && <button onClick={() => setDriverDialog(d)} className="text-sm text-slate-600 underline">Edit</button>}
              </div>
              <ul className="mt-3 space-y-1 text-sm">
                {d.vehicles.map((v) => (
                  <li key={v.id} className="flex items-center gap-2">
                    <span className="inline-block h-3 w-3 rounded-full border border-slate-300" style={{ background: v.colour }} />
                    <span className="capitalize">{[v.colour, v.make, v.model].filter(Boolean).join(" ")}</span>
                    <span className="text-[var(--fos-text-muted)]">· {v.vehicle_type} · {v.seats} seats{v.registration ? ` · ${v.registration}` : ""}</span>
                  </li>
                ))}
                {d.vehicles.length === 0 && <li className="text-[var(--fos-text-muted)]">No car added yet.</li>}
              </ul>
              {manage && (
                <div className="mt-3 flex gap-2 text-sm">
                  <button onClick={() => setCarFor(d)} className="rounded-lg border border-slate-300 px-3 py-1.5">Add car</button>
                  <button onClick={() => makeLink(d)} className="flex items-center gap-1 rounded-lg border border-slate-300 px-3 py-1.5"><Link2 size={14} /> {d.has_link ? "New private link" : "Private link"}</button>
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      {assigning && <AssignDialog job={assigning} onClose={() => setAssigning(null)} onDone={(msg) => { setAssigning(null); setNotice(msg); load(); }} />}
      {newJobs && <JobsDialog presetCase={caseParam} onClose={() => setNewJobs(false)} onDone={() => { setNewJobs(false); setTab("jobs"); load(); }} />}
      {driverDialog && <DriverDialog driver={driverDialog === "new" ? null : driverDialog} onClose={() => setDriverDialog(null)} onDone={() => { setDriverDialog(null); load(); }} />}
      {carFor && <CarDialog driver={carFor} onClose={() => setCarFor(null)} onDone={() => { setCarFor(null); load(); }} />}
    </main>
  );
}

function AssignDialog({ job, onClose, onDone }: { job: Job; onClose: () => void; onDone: (m: string) => void }) {
  const [list, setList] = useState<Candidate[] | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    api.get<Candidate[]>(`/transport/jobs/${job.id}/candidates`).then((r) => setList(r.data)).catch((e) => setError(getApiErrorMessage(e, "Could not load drivers.")));
  }, [job.id]);

  async function pick(c: Candidate) {
    try {
      const r = await api.post(`/transport/jobs/${job.id}/assign`, { driver_id: c.driver_id, vehicle_id: c.vehicle.id });
      onDone(r.data.alert.emailed ? `${c.driver_name} was emailed the details.` : `${c.driver_name} is assigned. Send the alert with the WhatsApp button.`);
    } catch (e) {
      setError(getApiErrorMessage(e, "Could not assign."));
    }
  }

  return (
    <Dialog title="Choose a driver" onClose={onClose}>
      <p className="mb-3 text-sm text-slate-500">Free drivers whose car fits: {[job.required_colour, job.required_type, job.required_model].filter(Boolean).join(" ") || "any car"}.</p>
      {error && <p role="alert" className="mb-3 rounded-lg bg-red-50 p-3 text-sm text-red-700">{error}</p>}
      {!list && <Loader2 className="animate-spin" />}
      {list?.length === 0 && <p className="text-sm text-slate-600">Nobody free has a matching car. Add a driver, or change what the job asks for.</p>}
      <ul className="divide-y divide-slate-100">
        {list?.map((c) => (
          <li key={`${c.driver_id}${c.vehicle.id}`} className="flex items-center justify-between gap-3 py-3">
            <div>
              <p className="font-medium">{c.driver_name}</p>
              <p className="text-sm capitalize text-slate-500">{[c.vehicle.colour, c.vehicle.make, c.vehicle.model].filter(Boolean).join(" ")} · {c.vehicle.vehicle_type}</p>
            </div>
            <button onClick={() => pick(c)} className="rounded-lg bg-slate-900 px-3 py-2 text-sm font-medium text-white">Assign</button>
          </li>
        ))}
      </ul>
    </Dialog>
  );
}

function JobsDialog({ presetCase, onClose, onDone }: { presetCase: string | null; onClose: () => void; onDone: () => void }) {
  const [cases, setCases] = useState<CaseRow[]>([]);
  const [caseId, setCaseId] = useState(presetCase ?? "");
  const [count, setCount] = useState("1");
  const [colour, setColour] = useState("");
  const [type, setType] = useState("");
  const [model, setModel] = useState("");
  const [at, setAt] = useState("");
  const [pickup, setPickup] = useState("");
  const [venue, setVenue] = useState("");
  const [dest, setDest] = useState("");
  const [dress, setDress] = useState("");
  const [notes, setNotes] = useState("");
  const [pay, setPay] = useState("");
  const [label, setLabel] = useState("Family car");
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    api.get<CaseRow[]>("/cases").then((r) => setCases(r.data.filter((c) => !!c.funeral_date))).catch(() => setCases([]));
  }, []);

  function chooseCase(id: string) {
    setCaseId(id);
    const c = cases.find((x) => x.id === id);
    if (c?.funeral_date && !at) setAt(`${c.funeral_date.slice(0, 10)}T08:00`);
    if (c?.funeral_venue && !venue) setVenue(c.funeral_venue);
  }

  async function submit(e: FormEvent) {
    e.preventDefault();
    setSaving(true);
    setError("");
    try {
      await api.post(`/cases/${caseId}/transport-jobs`, {
        label, count: Number(count) || 1,
        required_colour: colour || null, required_type: type || null, required_model: model || null,
        report_time: new Date(at).toISOString(),
        pickup_address: pickup || null, venue: venue || null, destination: dest || null,
        dress_code: dress || null, instructions: notes || null, pay_amount: pay || "0",
      });
      onDone();
    } catch (err) {
      setError(getApiErrorMessage(err, "Could not create the jobs."));
      setSaving(false);
    }
  }

  return (
    <Dialog title="Car jobs for a funeral" onClose={onClose} wide>
      <form onSubmit={submit} className="space-y-4">
        {error && <p role="alert" className="rounded-lg bg-red-50 p-3 text-sm text-red-700">{error}</p>}
        <label className="block text-sm font-medium">Funeral
          <select required className={inputClass} value={caseId} onChange={(e) => chooseCase(e.target.value)}>
            <option value="">Choose a funeral…</option>
            {cases.map((c) => <option key={c.id} value={c.id}>{c.deceased_full_name} · {c.case_number} · {c.funeral_date?.slice(0, 10)}</option>)}
            {presetCase && !cases.some((c) => c.id === presetCase) && <option value={presetCase}>This funeral</option>}
          </select>
        </label>
        <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
          <label className="block text-sm font-medium">What for<input className={inputClass} value={label} onChange={(e) => setLabel(e.target.value)} /></label>
          <label className="block text-sm font-medium">How many cars<input inputMode="numeric" className={inputClass} value={count} onChange={(e) => setCount(e.target.value)} /></label>
          <label className="block text-sm font-medium">Colour<input className={inputClass} placeholder="black" value={colour} onChange={(e) => setColour(e.target.value)} /></label>
          <label className="block text-sm font-medium">Type
            <select className={inputClass} value={type} onChange={(e) => setType(e.target.value)}>
              <option value="">Any</option>
              {TYPES.map((t) => <option key={t}>{t}</option>)}
            </select>
          </label>
        </div>
        <div className="grid grid-cols-2 gap-3">
          <label className="block text-sm font-medium">Model (optional)<input className={inputClass} placeholder="e.g. Quantum" value={model} onChange={(e) => setModel(e.target.value)} /></label>
          <label className="block text-sm font-medium">Report at<input required type="datetime-local" className={inputClass} value={at} onChange={(e) => setAt(e.target.value)} /></label>
        </div>
        <div className="grid grid-cols-2 gap-3">
          <label className="block text-sm font-medium">Pick up from<input className={inputClass} value={pickup} onChange={(e) => setPickup(e.target.value)} /></label>
          <label className="block text-sm font-medium">Venue<input className={inputClass} value={venue} onChange={(e) => setVenue(e.target.value)} /></label>
          <label className="block text-sm font-medium">Then to (cemetery)<input className={inputClass} value={dest} onChange={(e) => setDest(e.target.value)} /></label>
          <label className="block text-sm font-medium">Dress code<input className={inputClass} placeholder="Black suit, white gloves" value={dress} onChange={(e) => setDress(e.target.value)} /></label>
        </div>
        <div className="grid grid-cols-2 gap-3">
          <label className="block text-sm font-medium">Pay per driver (R)<input inputMode="decimal" className={inputClass} value={pay} onChange={(e) => setPay(e.target.value)} /></label>
          <label className="block text-sm font-medium">Notes for the driver<input className={inputClass} value={notes} onChange={(e) => setNotes(e.target.value)} /></label>
        </div>
        <button disabled={saving} className="w-full rounded-lg bg-slate-900 px-4 py-3 text-sm font-semibold text-white disabled:opacity-50">{saving ? "Saving…" : "Create jobs"}</button>
      </form>
    </Dialog>
  );
}

function DriverDialog({ driver, onClose, onDone }: { driver: Driver | null; onClose: () => void; onDone: () => void }) {
  const [name, setName] = useState(driver?.full_name ?? "");
  const [phone, setPhone] = useState(driver?.phone ?? "");
  const [email, setEmail] = useState(driver?.email ?? "");
  const [area, setArea] = useState(driver?.area ?? "");
  const [active, setActive] = useState(driver?.is_active ?? true);
  const [error, setError] = useState("");

  async function submit(e: FormEvent) {
    e.preventDefault();
    const body = { full_name: name, phone: phone || null, email: email || null, area: area || null };
    try {
      if (driver) await api.patch(`/transport/drivers/${driver.id}`, { ...body, is_active: active });
      else await api.post("/transport/drivers", body);
      onDone();
    } catch (err) {
      setError(getApiErrorMessage(err, "Could not save."));
    }
  }

  return (
    <Dialog title={driver ? "Edit driver" : "Add driver"} onClose={onClose}>
      <form onSubmit={submit} className="space-y-4">
        {error && <p role="alert" className="rounded-lg bg-red-50 p-3 text-sm text-red-700">{error}</p>}
        <label className="block text-sm font-medium">Full name<input required className={inputClass} value={name} onChange={(e) => setName(e.target.value)} /></label>
        <label className="block text-sm font-medium">Phone (WhatsApp)<input className={inputClass} value={phone} onChange={(e) => setPhone(e.target.value)} /></label>
        <label className="block text-sm font-medium">Email<input type="email" className={inputClass} value={email} onChange={(e) => setEmail(e.target.value)} /></label>
        <label className="block text-sm font-medium">Area<input className={inputClass} value={area} onChange={(e) => setArea(e.target.value)} /></label>
        {driver && <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={active} onChange={(e) => setActive(e.target.checked)} /> Available for jobs</label>}
        <button className="w-full rounded-lg bg-slate-900 px-4 py-3 text-sm font-semibold text-white">Save</button>
      </form>
    </Dialog>
  );
}

function CarDialog({ driver, onClose, onDone }: { driver: Driver; onClose: () => void; onDone: () => void }) {
  const [make, setMake] = useState("");
  const [model, setModel] = useState("");
  const [type, setType] = useState("sedan");
  const [colour, setColour] = useState("");
  const [reg, setReg] = useState("");
  const [seats, setSeats] = useState("4");
  const [error, setError] = useState("");

  async function submit(e: FormEvent) {
    e.preventDefault();
    try {
      await api.post(`/transport/drivers/${driver.id}/vehicles`, {
        make: make || null, model: model || null, vehicle_type: type, colour,
        registration: reg || null, seats: Number(seats) || 4,
      });
      onDone();
    } catch (err) {
      setError(getApiErrorMessage(err, "Could not save."));
    }
  }

  return (
    <Dialog title={`Add a car for ${driver.full_name}`} onClose={onClose}>
      <form onSubmit={submit} className="space-y-4">
        {error && <p role="alert" className="rounded-lg bg-red-50 p-3 text-sm text-red-700">{error}</p>}
        <div className="grid grid-cols-2 gap-3">
          <label className="block text-sm font-medium">Colour<input required className={inputClass} placeholder="black" value={colour} onChange={(e) => setColour(e.target.value)} /></label>
          <label className="block text-sm font-medium">Type
            <select className={inputClass} value={type} onChange={(e) => setType(e.target.value)}>{TYPES.map((t) => <option key={t}>{t}</option>)}</select>
          </label>
          <label className="block text-sm font-medium">Make<input className={inputClass} value={make} onChange={(e) => setMake(e.target.value)} /></label>
          <label className="block text-sm font-medium">Model<input className={inputClass} value={model} onChange={(e) => setModel(e.target.value)} /></label>
          <label className="block text-sm font-medium">Registration<input className={inputClass} value={reg} onChange={(e) => setReg(e.target.value)} /></label>
          <label className="block text-sm font-medium">Seats<input inputMode="numeric" className={inputClass} value={seats} onChange={(e) => setSeats(e.target.value)} /></label>
        </div>
        <button className="w-full rounded-lg bg-slate-900 px-4 py-3 text-sm font-semibold text-white">Save car</button>
      </form>
    </Dialog>
  );
}
