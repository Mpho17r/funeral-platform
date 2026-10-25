"use client";

import { useCallback, useEffect, useState } from "react";
import { Check, Copy, Loader2 } from "lucide-react";

import api from "@/lib/api";
import { getApiErrorMessage } from "@/lib/format";
import { Dialog } from "@/components/Dialog";
import { ErrorNote } from "@/components/Notices";

type Link = {
  id: string;
  expires_at: string;
  revoked_at: string | null;
  last_used_at: string | null;
  created_at: string;
};

/** Make, copy and revoke private portal links for a funeral or a member. */
export function PortalLinkDialog({
  kind,
  targetId,
  label,
  onClose,
}: {
  kind: "family" | "member";
  targetId: string;
  label: string;
  onClose: () => void;
}) {
  const [links, setLinks] = useState<Link[]>([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [fresh, setFresh] = useState("");
  const [copied, setCopied] = useState(false);

  const param = kind === "family" ? "case_id" : "member_id";

  const load = useCallback(async () => {
    try {
      const r = await api.get<Link[]>("/portal-links", {
        params: { [param]: targetId },
      });
      setLinks(r.data);
    } catch (err) {
      setError(getApiErrorMessage(err, "Could not load the links."));
    } finally {
      setLoading(false);
    }
  }, [param, targetId]);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void load();
  }, [load]);

  async function create() {
    try {
      setBusy(true);
      setError("");
      const r = await api.post<{ path: string }>("/portal-links", {
        kind,
        [param]: targetId,
      });
      setFresh(`${window.location.origin}${r.data.path}`);
      setCopied(false);
      await load();
    } catch (err) {
      setError(getApiErrorMessage(err, "Could not create the link."));
    } finally {
      setBusy(false);
    }
  }

  async function revoke(id: string) {
    try {
      await api.delete(`/portal-links/${id}`);
      await load();
    } catch (err) {
      setError(getApiErrorMessage(err, "Could not revoke the link."));
    }
  }

  async function copy() {
    try {
      await navigator.clipboard.writeText(fresh);
      setCopied(true);
    } catch {
      setError("Copy failed. Select the link and copy it by hand.");
    }
  }

  const active = links.filter(
    (l) => !l.revoked_at && new Date(l.expires_at) > new Date(),
  );

  return (
    <Dialog
      title={kind === "family" ? "Family link" : "Member link"}
      onClose={onClose}
    >
      <div className="space-y-4">
        <p className="text-sm text-slate-600">
          A private link for {label}.{" "}
          {kind === "family"
            ? "It shows the funeral schedule, the balance and issued documents."
            : "It shows their membership, contributions and payments."}{" "}
          Anyone with the link can see this, so send it only to them. It
          expires after 30 days and you can switch it off at any time.
        </p>

        {error && <ErrorNote message={error} />}

        {fresh && (
          <div className="rounded-lg border border-emerald-200 bg-emerald-50 p-3">
            <p className="text-xs font-medium text-emerald-800">
              New link. It is shown only now, so copy it.
            </p>
            <input
              readOnly
              value={fresh}
              onFocus={(e) => e.currentTarget.select()}
              className="mt-2 w-full rounded border border-emerald-300 bg-white px-2 py-1.5 text-xs"
            />
            <div className="mt-2 flex gap-2">
              <button
                type="button"
                onClick={() => void copy()}
                className="flex items-center gap-1.5 rounded-lg bg-slate-900 px-3 py-2 text-sm font-semibold text-white"
              >
                {copied ? <Check size={15} /> : <Copy size={15} />}
                {copied ? "Copied" : "Copy"}
              </button>
              <a
                href={`https://wa.me/?text=${encodeURIComponent(fresh)}`}
                target="_blank"
                rel="noopener noreferrer"
                className="rounded-lg border border-slate-300 px-3 py-2 text-sm font-medium text-slate-800"
              >
                Send on WhatsApp
              </a>
            </div>
          </div>
        )}

        <button
          type="button"
          onClick={() => void create()}
          disabled={busy}
          className="flex items-center gap-2 rounded-lg bg-slate-900 px-4 py-2.5 text-sm font-semibold text-white disabled:opacity-60"
        >
          {busy && <Loader2 size={16} className="animate-spin" />}
          Create a new link
        </button>

        <div>
          <p className="mb-2 text-sm font-semibold text-slate-900">
            Active links
          </p>
          {loading ? (
            <Loader2 size={16} className="animate-spin text-slate-400" />
          ) : active.length === 0 ? (
            <p className="text-sm text-slate-500">None.</p>
          ) : (
            <ul className="space-y-2">
              {active.map((l) => (
                <li
                  key={l.id}
                  className="flex items-center justify-between rounded-lg border p-2.5 text-sm"
                >
                  <span className="text-slate-600">
                    Expires {new Date(l.expires_at).toLocaleDateString()}
                    {l.last_used_at
                      ? ` · opened ${new Date(l.last_used_at).toLocaleDateString()}`
                      : " · not opened yet"}
                  </span>
                  <button
                    type="button"
                    onClick={() => void revoke(l.id)}
                    className="font-medium text-red-700 hover:underline"
                  >
                    Switch off
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </Dialog>
  );
}
