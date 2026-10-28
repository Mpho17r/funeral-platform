"use client";

import { ChevronRight, Compass } from "lucide-react";
import { useRouter } from "next/navigation";

import { useCurrentUser } from "@/components/CurrentUserProvider";
import { useTour } from "@/components/GuidedTour";
import { TOURS, tourForRole } from "@/lib/tours";

type Topic = {
  title: string;
  summary: string;
  steps: string[];
  links: { label: string; path: string }[];
};

const TOPICS: Topic[] = [
  {
    title: "Registering a death",
    summary: "From the first call to a case on the system.",
    steps: [
      "Open Cases and choose New case. Enter the case number, the deceased's name and next of kin.",
      "If the person was a member, link the case to their policy. Cover is then checked against the date of death and the waiting periods on their plan.",
      "Fill in the death record (date and cause). The cause decides which waiting period applies.",
      "Record the body coming in under Mortuary: who brought it, what came with it, and which fridge or space it is in.",
    ],
    links: [
      { label: "Cases", path: "/cases" },
      { label: "Mortuary", path: "/mortuary" },
    ],
  },
  {
    title: "Arranging the funeral",
    summary: "Meeting the family and planning the day.",
    steps: [
      "Open the case and go to Arrangements to record what the family has chosen.",
      "Add the services and items on the case so the amount owing is worked out.",
      "Book vehicles and people under Schedule so nothing is double-booked.",
      "The Run sheet shows the day's order: collections, the service and the burial. Check it the evening before.",
    ],
    links: [
      { label: "Run sheet", path: "/run-sheet" },
      { label: "Schedule", path: "/resource-bookings" },
      { label: "Services", path: "/services" },
    ],
  },
  {
    title: "Taking money on a case",
    summary: "Invoices, payments and what is still owed.",
    steps: [
      "Issue an invoice from the case once the services are agreed. An issued invoice is permanent: if it was wrong, void it and issue a new one.",
      "Record each payment against the case as it comes in. The balance updates straight away.",
      "The dashboard shows how much is still to collect across all cases.",
    ],
    links: [{ label: "Dashboard", path: "/dashboard" }],
  },
  {
    title: "Running memberships",
    summary: "Plans, contributions, arrears and claims.",
    steps: [
      "Create plans under Membership Plans, including the waiting periods for natural, accidental and suicide deaths.",
      "Add members, then give each a membership on a plan. Add covered dependents and beneficiaries to the policy.",
      "Record contributions as they are paid. A member who misses a due date moves to arrears, and later lapses, following your rules in Settings.",
      "Reminders are prepared for you but never sent automatically. Open Reminders, send each one by WhatsApp, SMS or email, then mark it sent.",
      "A claim can only be paid when the beneficiary shares add up to 100%.",
    ],
    links: [
      { label: "Membership Plans", path: "/membership-plans" },
      { label: "Memberships", path: "/memberships" },
      { label: "Reminders", path: "/communications" },
      { label: "Claims", path: "/claims" },
    ],
  },
  {
    title: "Getting your existing records in",
    summary: "Moving over from spreadsheets or another system.",
    steps: [
      "Use Import data. Work in this order: members and policies, payment history, covered dependents and beneficiaries, then open cases.",
      "Each import checks your file first and shows every problem. Nothing is saved until you confirm.",
      "Fix the rows with problems in your file and upload it again. Rows already imported are skipped.",
    ],
    links: [{ label: "Import data", path: "/import" }],
  },
  {
    title: "Who can do what",
    summary: "Roles and access.",
    steps: [
      "Give every person their own sign-in under Settings → Team. Never share a login: the audit trail records who did what.",
      "Managers and staff see only what their role allows. The main administrator can adjust this.",
      "Click your name at the bottom of the sidebar to change your own name and job title.",
    ],
    links: [
      { label: "Team", path: "/settings/team" },
      { label: "Settings", path: "/settings" },
    ],
  },
  {
    title: "Keeping records safe",
    summary: "Nothing important disappears by accident.",
    steps: [
      "Members and cases are archived, not deleted. An archived record can be restored.",
      "The Audit trail shows who changed what and when, including sign-ins and exports. Personal details are kept out of it.",
      "If someone asks for a copy of everything you hold about them, or asks to be removed, a member record has both options on its page.",
    ],
    links: [{ label: "Audit trail", path: "/audit" }],
  },
];

export default function HelpPage() {
  const router = useRouter();
  const { start } = useTour();
  const { user } = useCurrentUser();
  const mine = tourForRole(user?.role);

  return (
    <main className="min-h-screen bg-[var(--fos-page)] text-[var(--fos-text)]">
      <section className="mx-auto max-w-3xl p-6 md:p-8">
        <h1 className="text-2xl font-bold">Guide</h1>
        <p className="mt-1 text-sm text-[var(--fos-text-muted)]">
          How a funeral home runs on FuneralOS, in the order you will meet
          things. Open any topic.
        </p>

        <div className="mt-6 rounded-2xl border border-[var(--fos-border)] bg-[var(--fos-surface)] p-5">
          <div className="flex items-center gap-2 font-semibold">
            <Compass size={18} /> Guided tours
          </div>
          <p className="mt-1 text-sm text-[var(--fos-text-muted)]">
            Click-through lessons that follow a funeral from the first call to a
            completed case. Yours is highlighted.
          </p>
          <div className="mt-3 grid gap-2 sm:grid-cols-2">
            {TOURS.map((t) => (
              <button
                key={t.id}
                type="button"
                onClick={() => start(t.id)}
                className={`rounded-xl border p-3 text-left hover:bg-[var(--fos-surface-muted)] ${
                  t.id === mine.id ? "border-slate-900" : "border-[var(--fos-border)]"
                }`}
              >
                <span className="block text-sm font-semibold">
                  {t.title}
                  {t.id === mine.id ? " (yours)" : ""}
                </span>
                <span className="block text-xs text-[var(--fos-text-muted)]">
                  {t.summary}
                </span>
              </button>
            ))}
          </div>
        </div>

        <div className="mt-6 space-y-3">
          {TOPICS.map((topic, index) => (
            <details
              key={topic.title}
              open={index === 0}
              className="group rounded-2xl border border-[var(--fos-border)] bg-[var(--fos-surface)] p-5"
            >
              <summary className="flex cursor-pointer list-none items-center justify-between gap-3">
                <span>
                  <span className="block font-semibold">{topic.title}</span>
                  <span className="block text-sm text-[var(--fos-text-muted)]">
                    {topic.summary}
                  </span>
                </span>
                <ChevronRight
                  size={18}
                  className="shrink-0 text-[var(--fos-text-muted)] transition group-open:rotate-90"
                />
              </summary>

              <ol className="mt-4 list-decimal space-y-2 pl-5 text-sm leading-6 text-[var(--fos-text-secondary)]">
                {topic.steps.map((step) => (
                  <li key={step}>{step}</li>
                ))}
              </ol>

              <div className="mt-4 flex flex-wrap gap-2">
                {topic.links.map((link) => (
                  <button
                    key={link.path}
                    type="button"
                    onClick={() => router.push(link.path)}
                    className="rounded-lg border border-[var(--fos-border)] px-3 py-1.5 text-sm font-medium transition hover:bg-[var(--fos-surface-muted)]"
                  >
                    {link.label} →
                  </button>
                ))}
              </div>
            </details>
          ))}
        </div>
      </section>
    </main>
  );
}
