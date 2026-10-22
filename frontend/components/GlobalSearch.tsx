"use client";

import { useRouter } from "next/navigation";
import { createPortal } from "react-dom";
import { useEffect, useMemo, useRef, useState } from "react";
import { Loader2, Search, X } from "lucide-react";

import api from "@/lib/api";

type Item = { id: string; title: string; subtitle: string; href: string };
type Group = { key: string; label: string; items: Item[] };

/**
 * One search box for everything the person is allowed to open.
 * Opens from the top bar or with Ctrl/Cmd+K; arrows and Enter work.
 */
export function GlobalSearch({ compact = false }: { compact?: boolean }) {
  const router = useRouter();
  const inputRef = useRef<HTMLInputElement>(null);

  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [result, setResult] = useState<{ q: string; groups: Group[] } | null>(
    null,
  );
  const [loading, setLoading] = useState(false);
  const [failed, setFailed] = useState(false);
  const [active, setActive] = useState(0);

  const flat = useMemo(
    () => (result ? result.groups.flatMap((g) => g.items) : []),
    [result],
  );

  function close() {
    setOpen(false);
    setQuery("");
    setResult(null);
    setFailed(false);
    setActive(0);
  }

  // The desktop box owns the shortcut; the phone icon is a second copy.
  useEffect(() => {
    if (compact) return;

    function onKey(event: KeyboardEvent) {
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        setOpen((current) => !current);
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [compact]);

  useEffect(() => {
    if (open) inputRef.current?.focus();
  }, [open]);

  // Search a moment after the person stops typing.
  useEffect(() => {
    const text = query.trim();
    if (text.length < 2) {
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setResult(null);
      setLoading(false);
      return;
    }

    let cancelled = false;
    setLoading(true);

    const timer = window.setTimeout(() => {
      api
        .get<{ query: string; groups: Group[] }>("/search", {
          params: { q: text },
        })
        .then((response) => {
          if (cancelled) return;
          setResult({ q: text, groups: response.data.groups });
          setFailed(false);
          setActive(0);
        })
        .catch(() => {
          if (!cancelled) setFailed(true);
        })
        .finally(() => {
          if (!cancelled) setLoading(false);
        });
    }, 250);

    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
  }, [query]);

  function go(item: Item) {
    close();
    router.push(item.href);
  }

  function onKeyDown(event: React.KeyboardEvent) {
    if (event.key === "Escape") {
      close();
    } else if (event.key === "ArrowDown") {
      event.preventDefault();
      setActive((i) => Math.min(i + 1, Math.max(flat.length - 1, 0)));
    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      setActive((i) => Math.max(i - 1, 0));
    } else if (event.key === "Enter" && flat[active]) {
      event.preventDefault();
      go(flat[active]);
    }
  }

  const trimmed = query.trim();
  let index = -1;

  return (
    <>
      {compact ? (
        <button
          type="button"
          aria-label="Search"
          onClick={() => setOpen(true)}
          className="flex h-10 w-10 items-center justify-center rounded-lg text-[var(--fos-text-secondary)] hover:bg-[var(--fos-surface-muted)]"
        >
          <Search size={20} />
        </button>
      ) : (
        <button
          type="button"
          onClick={() => setOpen(true)}
          className="flex w-full max-w-md items-center gap-2 rounded-lg border border-[var(--fos-border)] bg-[var(--fos-page)] px-3 py-2 text-sm text-[var(--fos-text-muted)] hover:border-[var(--fos-text-muted)]"
        >
          <Search size={16} />
          <span className="flex-1 text-left">
            Search funerals, members, families…
          </span>
          <kbd className="rounded border border-[var(--fos-border)] px-1.5 text-xs">
            Ctrl K
          </kbd>
        </button>
      )}

      {open &&
        createPortal(
          <div
            className="fixed inset-0 z-[200] flex items-start justify-center bg-slate-950/50 px-4 pt-[10vh]"
            onMouseDown={(event) => {
              if (event.target === event.currentTarget) close();
            }}
          >
            <div
              role="dialog"
              aria-label="Search"
              className="w-full max-w-xl overflow-hidden rounded-2xl border border-[var(--fos-border)] bg-[var(--fos-surface)] shadow-2xl"
            >
              <div className="flex items-center gap-3 border-b border-[var(--fos-border)] px-4">
                <Search size={18} className="text-[var(--fos-text-muted)]" />
                <input
                  ref={inputRef}
                  value={query}
                  onChange={(event) => setQuery(event.target.value)}
                  onKeyDown={onKeyDown}
                  placeholder="Name, case number, member number, phone…"
                  aria-label="Search"
                  style={{ outline: "none", boxShadow: "none", border: 0 }}
                  className="h-14 flex-1 bg-transparent text-base text-[var(--fos-text)] outline-none placeholder:text-[var(--fos-text-muted)]"
                />
                {loading && (
                  <Loader2
                    size={16}
                    className="animate-spin text-[var(--fos-text-muted)]"
                  />
                )}
                <button
                  type="button"
                  aria-label="Close search"
                  onClick={close}
                  className="text-[var(--fos-text-muted)]"
                >
                  <X size={18} />
                </button>
              </div>

              <div className="max-h-[60vh] overflow-y-auto">
                {trimmed.length < 2 && (
                  <p className="p-5 text-sm text-[var(--fos-text-muted)]">
                    Type at least two letters. You only see what you are allowed
                    to open.
                  </p>
                )}

                {failed && (
                  <p className="p-5 text-sm text-red-600">
                    Search is not available right now.
                  </p>
                )}

                {!failed &&
                  result &&
                  result.q === trimmed &&
                  result.groups.length === 0 && (
                    <p className="p-5 text-sm text-[var(--fos-text-muted)]">
                      Nothing found for “{trimmed}”.
                    </p>
                  )}

                {!failed &&
                  result?.groups.map((group) => (
                    <div key={group.key}>
                      <p className="px-4 pb-1 pt-3 text-xs font-semibold uppercase tracking-wide text-[var(--fos-text-muted)]">
                        {group.label}
                      </p>
                      {group.items.map((item) => {
                        index += 1;
                        const here = index;
                        return (
                          <button
                            key={item.id}
                            type="button"
                            onMouseEnter={() => setActive(here)}
                            onClick={() => go(item)}
                            className={`block w-full px-4 py-2.5 text-left ${
                              active === here
                                ? "bg-[var(--fos-surface-muted)]"
                                : ""
                            }`}
                          >
                            <span className="block text-sm font-medium text-[var(--fos-text)]">
                              {item.title}
                            </span>
                            {item.subtitle && (
                              <span className="block text-xs text-[var(--fos-text-muted)]">
                                {item.subtitle}
                              </span>
                            )}
                          </button>
                        );
                      })}
                    </div>
                  ))}
              </div>
            </div>
          </div>,
          document.body,
        )}
    </>
  );
}
