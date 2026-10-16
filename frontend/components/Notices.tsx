"use client";

import { X } from "lucide-react";

export function Banner({
  tone,
  children,
  onDismiss,
}: {
  tone: "error" | "success";
  children: React.ReactNode;
  onDismiss: () => void;
}) {
  const style =
    tone === "error"
      ? "border-red-200 bg-red-50 text-red-700"
      : "border-emerald-200 bg-emerald-50 text-emerald-700";

  return (
    <div
      role={tone === "error" ? "alert" : "status"}
      className={`flex items-center justify-between rounded-lg border px-4 py-3 text-sm ${style}`}
    >
      <span>{children}</span>

      <button
        type="button"
        onClick={onDismiss}
        aria-label="Dismiss"
        className="ml-4"
      >
        <X size={18} />
      </button>
    </div>
  );
}

export function ErrorNote({ message }: { message: string }) {
  return (
    <p
      role="alert"
      className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700"
    >
      {message}
    </p>
  );
}
