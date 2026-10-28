"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";
import { usePathname, useRouter } from "next/navigation";
import { ArrowLeft, ArrowRight, Compass, X } from "lucide-react";

import api from "@/lib/api";
import { permissionForPath } from "@/lib/access";
import { TOURS, tourForRole, type Tour, type TourStep } from "@/lib/tours";
import { useCurrentUser } from "@/components/CurrentUserProvider";

type TourContextValue = {
  start: (tourId?: string) => void;
};

const TourContext = createContext<TourContextValue>({ start: () => {} });

export function useTour() {
  return useContext(TourContext);
}

type Box = { top: number; left: number; width: number; height: number };

function storageKey(userId: string) {
  return `fos.tour.${userId}`;
}

function readOffered(userId: string): boolean {
  try {
    return window.localStorage.getItem(storageKey(userId)) === "offered";
  } catch {
    return true; // storage blocked: never nag
  }
}

function markOffered(userId: string) {
  try {
    window.localStorage.setItem(storageKey(userId), "offered");
  } catch {
    /* ignore */
  }
}

/** The menu entry on screen (the desktop or the open mobile menu). */
function findNav(path: string): HTMLElement | null {
  const all = document.querySelectorAll<HTMLElement>(`[data-tour="${path}"]`);
  for (const el of Array.from(all)) {
    const r = el.getBoundingClientRect();
    if (r.width > 0 && r.height > 0) return el;
  }
  return null;
}

export function TourProvider({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const { user, access, can } = useCurrentUser();

  const [tour, setTour] = useState<Tour | null>(null);
  const [index, setIndex] = useState(0);
  const [offer, setOffer] = useState(false);
  const [caseId, setCaseId] = useState<string | null>(null);
  const [box, setBox] = useState<Box | null>(null);

  const userId = user?.user_id;

  // Offer the tour once, the first time someone signs in.
  useEffect(() => {
    if (!userId || !access) return;
    if (!readOffered(userId)) {
      markOffered(userId);
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setOffer(true);
    }
  }, [userId, access]);

  const steps: TourStep[] = useMemo(() => {
    if (!tour) return [];
    return tour.steps.filter((s) => {
      const page = s.caseSub !== undefined ? "/cases" : (s.path ?? s.nav ?? "");
      const needed = page ? permissionForPath(page) : null;
      return !needed || can(needed);
    });
  }, [tour, can]);

  const step = tour ? steps[Math.min(index, steps.length - 1)] : null;

  const target = useMemo(() => {
    if (!step) return null;
    if (step.caseSub !== undefined) {
      if (!caseId) return "/cases";
      return `/cases/${caseId}${step.caseSub ? `/${step.caseSub}` : ""}`;
    }
    return step.path ?? null;
  }, [step, caseId]);

  const start = useCallback(
    (tourId?: string) => {
      const chosen =
        TOURS.find((t) => t.id === tourId) ?? tourForRole(user?.role);
      setOffer(false);
      setIndex(0);
      setTour(chosen);
      api
        .get<{ id: string }[]>("/cases")
        .then((r) => setCaseId(r.data[0]?.id ?? null))
        .catch(() => setCaseId(null));
    },
    [user?.role],
  );

  const stop = useCallback(() => {
    setTour(null);
    setBox(null);
  }, []);

  const next = useCallback(() => {
    setIndex((i) => {
      if (i + 1 >= steps.length) {
        stop();
        return 0;
      }
      return i + 1;
    });
  }, [steps.length, stop]);

  // Open the page each step is about.
  useEffect(() => {
    if (tour && target && pathname !== target) router.push(target);
    // Only when the step changes, not on every click around the page.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tour, target]);

  // Follow the highlighted menu item as the page moves or resizes.
  useEffect(() => {
    if (!tour || !step?.nav) {
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setBox(null);
      return;
    }
    const nav = step.nav;
    function measure() {
      const el = findNav(nav);
      if (!el) return setBox(null);
      const r = el.getBoundingClientRect();
      setBox({ top: r.top, left: r.left, width: r.width, height: r.height });
    }
    measure();
    const timer = window.setInterval(measure, 400);
    window.addEventListener("resize", measure);
    return () => {
      window.clearInterval(timer);
      window.removeEventListener("resize", measure);
    };
  }, [tour, step]);

  // "Click here" steps move on when the person clicks the menu item.
  useEffect(() => {
    if (!tour || !step?.click || !step.nav) return;
    const el = findNav(step.nav);
    if (!el) return;
    const handler = () => next();
    el.addEventListener("click", handler, { once: true });
    return () => el.removeEventListener("click", handler);
  }, [tour, step, box, next]);

  useEffect(() => {
    if (!tour) return;
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") stop();
    }
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [tour, stop]);

  const value = useMemo(() => ({ start }), [start]);
  const last = steps.length > 0 && index >= steps.length - 1;
  const noCase =
    step?.caseSub !== undefined && !caseId
      ? " (You have no cases yet. Create one and this page will open with it.)"
      : "";

  return (
    <TourContext.Provider value={value}>
      {children}

      {offer && !tour && (
        <div
          role="dialog"
          aria-label="Take the tour"
          className="fixed bottom-4 right-4 z-[200] w-[min(92vw,22rem)] rounded-2xl border bg-white p-5 shadow-2xl"
        >
          <div className="flex items-center gap-2 text-slate-900">
            <Compass size={18} />
            <p className="font-semibold">New here? Take the tour</p>
          </div>
          <p className="mt-2 text-sm text-slate-600">
            A few minutes, click by click, from the first call to a completed
            case. It is matched to your role.
          </p>
          <div className="mt-4 flex gap-2">
            <button
              type="button"
              onClick={() => start()}
              className="rounded-lg bg-slate-900 px-4 py-2 text-sm font-medium text-white"
            >
              Start the tour
            </button>
            <button
              type="button"
              onClick={() => setOffer(false)}
              className="rounded-lg border px-4 py-2 text-sm text-slate-700"
            >
              Not now
            </button>
          </div>
          <p className="mt-3 text-xs text-slate-500">
            You can find it later on the Guide page.
          </p>
        </div>
      )}

      {tour && step && (
        <>
          {box && (
            <div
              aria-hidden
              className="pointer-events-none fixed z-[190] rounded-xl ring-4 ring-amber-400"
              style={{
                top: box.top - 4,
                left: box.left - 4,
                width: box.width + 8,
                height: box.height + 8,
                boxShadow: "0 0 0 9999px rgba(15,23,42,0.5)",
              }}
            />
          )}
          <div
            role="dialog"
            aria-live="polite"
            aria-label={step.title}
            className="fixed z-[200] w-[min(92vw,24rem)] rounded-2xl border bg-white p-5 shadow-2xl"
            style={
              box && window.innerWidth >= 640
                ? {
                    left: box.left + box.width + 20,
                    top: Math.max(
                      12,
                      Math.min(box.top - 8, window.innerHeight - 320),
                    ),
                  }
                : { right: 16, bottom: 16 }
            }
          >
            <div className="flex items-start justify-between gap-3">
              <p className="text-xs font-medium text-slate-500">
                {tour.title} · {Math.min(index + 1, steps.length)} of {steps.length}
              </p>
              <button
                type="button"
                onClick={stop}
                aria-label="Skip the tour"
                className="-mr-1 -mt-1 rounded p-1 text-slate-500 hover:bg-slate-100"
              >
                <X size={16} />
              </button>
            </div>
            <h2 className="mt-1 text-base font-semibold text-slate-900">
              {step.title}
            </h2>
            <p className="mt-2 text-sm leading-6 text-slate-700">
              {step.body}
              {noCase}
            </p>
            {step.click && box && (
              <p className="mt-2 rounded-lg bg-amber-50 px-3 py-2 text-xs font-medium text-amber-800">
                Click the highlighted menu item to continue.
              </p>
            )}
            <div className="mt-4 flex items-center justify-between">
              <button
                type="button"
                disabled={index === 0}
                onClick={() => setIndex((i) => Math.max(0, i - 1))}
                className="flex items-center gap-1 rounded-lg border px-3 py-2 text-sm text-slate-700 disabled:opacity-40"
              >
                <ArrowLeft size={14} /> Back
              </button>
              <button
                type="button"
                onClick={next}
                className="flex items-center gap-1 rounded-lg bg-slate-900 px-4 py-2 text-sm font-medium text-white"
              >
                {last ? "Finish" : "Next"} <ArrowRight size={14} />
              </button>
            </div>
            <div className="mt-3 h-1 overflow-hidden rounded bg-slate-100">
              <div
                className="h-full bg-slate-900 transition-all"
                style={{ width: `${((index + 1) / Math.max(steps.length, 1)) * 100}%` }}
              />
            </div>
          </div>
        </>
      )}
    </TourContext.Provider>
  );
}
