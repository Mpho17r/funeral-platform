"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import {
  AlertTriangle,
  ArrowLeft,
  CheckCircle2,
  DatabaseBackup,
  Download,
  Loader2,
} from "lucide-react";

import api from "@/lib/api";
import { getApiErrorMessage } from "@/lib/format";
import { Banner } from "@/components/Notices";

type BackupStatus = {
  state: "ok" | "stale" | "failed" | "never" | "unknown";
  message: string;
  last_backup_at: string | null;
  age_hours: number | null;
  size_mb?: number | null;
  error?: string | null;
};

function describeAge(hours: number | null) {
  if (hours === null) return "";
  if (hours < 1) return "less than an hour ago";
  if (hours < 24) return `${Math.round(hours)} hours ago`;
  return `${Math.round(hours / 24)} days ago`;
}

export default function DataPage() {
  const router = useRouter();

  const [status, setStatus] = useState<BackupStatus | null>(null);
  const [statusError, setStatusError] = useState("");
  const [busy, setBusy] = useState<"data" | "files" | null>(null);
  const [message, setMessage] = useState<{
    tone: "error" | "success";
    text: string;
  } | null>(null);

  useEffect(() => {
    api
      .get<BackupStatus>("/data-export/backup-status")
      .then((response) => setStatus(response.data))
      .catch((err) =>
        setStatusError(getApiErrorMessage(err, "Could not check backups.")),
      );
  }, []);

  async function download(includeFiles: boolean) {
    setBusy(includeFiles ? "files" : "data");
    setMessage(null);

    try {
      const response = await api.post("/data-export", null, {
        params: { include_files: includeFiles },
        responseType: "blob",
      });

      const url = URL.createObjectURL(response.data as Blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = `funeralos-export-${new Date()
        .toISOString()
        .slice(0, 10)}.zip`;
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(url);

      setMessage({
        tone: "success",
        text: "Your export has downloaded. It holds personal information, so keep it somewhere safe.",
      });
    } catch (err) {
      setMessage({
        tone: "error",
        text: getApiErrorMessage(err, "The export could not be created."),
      });
    } finally {
      setBusy(null);
    }
  }

  const healthy = status?.state === "ok";

  return (
    <div className="mx-auto max-w-3xl space-y-6 p-6 md:p-8">
      <button
        type="button"
        onClick={() => router.push("/settings")}
        className="flex items-center gap-2 text-sm font-medium text-[var(--fos-text-muted)] hover:text-[var(--fos-text)]"
      >
        <ArrowLeft size={16} /> Back to Settings
      </button>

      <div>
        <h1 className="text-2xl font-bold text-[var(--fos-text)]">
          Data export and backups
        </h1>
        <p className="text-sm text-[var(--fos-text-muted)]">
          Your records belong to your business. Take a copy any time, and make
          sure automatic backups are running.
        </p>
      </div>

      {message && (
        <Banner tone={message.tone} onDismiss={() => setMessage(null)}>
          {message.text}
        </Banner>
      )}

      <section className="rounded-2xl border border-[var(--fos-border)] bg-[var(--fos-surface)] p-6 shadow-sm">
        <h2 className="flex items-center gap-2 text-lg font-semibold text-[var(--fos-text)]">
          <Download size={20} /> Download all your data
        </h2>
        <p className="mt-2 text-sm leading-6 text-[var(--fos-text-muted)]">
          A ZIP file with every funeral, member, membership, payment, expense
          and more as spreadsheets you can open in Excel. Passwords are never
          included. Each download is recorded in the audit trail.
        </p>

        <div className="mt-4 flex flex-wrap gap-3">
          <button
            type="button"
            disabled={busy !== null}
            onClick={() => download(false)}
            className="flex items-center gap-2 rounded-lg bg-[var(--fos-primary)] px-4 py-2.5 text-sm font-semibold text-[var(--fos-on-primary)] disabled:opacity-60"
          >
            {busy === "data" ? (
              <Loader2 size={16} className="animate-spin" />
            ) : (
              <Download size={16} />
            )}
            Download data
          </button>
          <button
            type="button"
            disabled={busy !== null}
            onClick={() => download(true)}
            className="flex items-center gap-2 rounded-lg border border-[var(--fos-border)] px-4 py-2.5 text-sm font-semibold text-[var(--fos-text)] hover:bg-[var(--fos-surface-muted)] disabled:opacity-60"
          >
            {busy === "files" && (
              <Loader2 size={16} className="animate-spin" />
            )}
            Data and uploaded files
          </button>
        </div>
        <p className="mt-2 text-xs text-[var(--fos-text-muted)]">
          Including files (documents, photos, logos) can make a large download.
        </p>
      </section>

      <section className="rounded-2xl border border-[var(--fos-border)] bg-[var(--fos-surface)] p-6 shadow-sm">
        <h2 className="flex items-center gap-2 text-lg font-semibold text-[var(--fos-text)]">
          <DatabaseBackup size={20} /> Automatic backups
        </h2>

        {statusError && (
          <p className="mt-3 text-sm text-red-600">{statusError}</p>
        )}

        {status && (
          <div
            className={`mt-3 flex items-start gap-3 rounded-xl border p-4 text-sm ${
              healthy
                ? "border-emerald-200 bg-emerald-50 text-emerald-800 dark:border-emerald-500/40 dark:bg-emerald-500/10 dark:text-emerald-200"
                : "border-amber-300 bg-amber-50 text-amber-900 dark:border-amber-500/40 dark:bg-amber-500/10 dark:text-amber-200"
            }`}
          >
            {healthy ? (
              <CheckCircle2 size={18} className="mt-0.5 shrink-0" />
            ) : (
              <AlertTriangle size={18} className="mt-0.5 shrink-0" />
            )}
            <div>
              <p className="font-semibold">{status.message}</p>
              {status.last_backup_at && (
                <p className="mt-0.5">
                  Last good backup {describeAge(status.age_hours)}
                  {status.size_mb ? ` (${status.size_mb} MB)` : ""}.
                </p>
              )}
              {status.error && (
                <p className="mt-0.5 break-words">Reason: {status.error}</p>
              )}
              {status.state === "never" && (
                <p className="mt-0.5">
                  Ask whoever runs your server to switch on the daily backup.
                </p>
              )}
            </div>
          </div>
        )}

        <p className="mt-4 text-sm leading-6 text-[var(--fos-text-muted)]">
          The backup copies the whole database and all uploaded files, checks
          the copy can be read back, and keeps the most recent 14. It runs on
          the server, not in this screen. Copy backups to a second place (an
          external drive or cloud storage) so one broken machine cannot take
          everything with it.
        </p>
      </section>
    </div>
  );
}
