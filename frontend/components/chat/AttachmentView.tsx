"use client";

import { useEffect, useState } from "react";
import { Download, FileText, Loader2 } from "lucide-react";

import api from "@/lib/api";
import { type Attachment, fileSize } from "@/components/chat/types";

async function fetchBlob(id: string): Promise<Blob> {
  const response = await api.get(`/chat/attachments/${id}`, {
    responseType: "blob",
  });
  return response.data as Blob;
}

/** A shared file. Pictures show inline; other files download on click.
 *  Files need the sign-in token, so they are fetched, not linked. */
export function AttachmentView({ file }: { file: Attachment }) {
  const [url, setUrl] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!file.is_image) return;

    let revoked = false;
    let objectUrl: string | null = null;

    fetchBlob(file.id)
      .then((blob) => {
        if (revoked) return;
        objectUrl = URL.createObjectURL(blob);
        setUrl(objectUrl);
      })
      .catch(() => {});

    return () => {
      revoked = true;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [file.id, file.is_image]);

  async function download() {
    setBusy(true);
    try {
      const blob = await fetchBlob(file.id);
      const link = document.createElement("a");
      link.href = URL.createObjectURL(blob);
      link.download = file.filename;
      link.click();
      URL.revokeObjectURL(link.href);
    } finally {
      setBusy(false);
    }
  }

  if (file.is_image) {
    return url ? (
      <button
        type="button"
        onClick={() => window.open(url, "_blank", "noopener")}
        className="block overflow-hidden rounded-xl"
        aria-label={`Open ${file.filename}`}
      >
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img
          src={url}
          alt={file.filename}
          className="max-h-60 max-w-full rounded-xl object-cover"
        />
      </button>
    ) : (
      <div className="flex h-24 w-40 items-center justify-center rounded-xl bg-black/10">
        <Loader2 size={18} className="animate-spin" />
      </div>
    );
  }

  return (
    <button
      type="button"
      onClick={download}
      className="flex items-center gap-3 rounded-xl border border-current/20 bg-black/5 px-3 py-2 text-left"
    >
      <FileText size={20} className="shrink-0" />
      <span className="min-w-0">
        <span className="block max-w-48 truncate text-sm font-medium">
          {file.filename}
        </span>
        <span className="block text-xs opacity-70">
          {fileSize(file.size_bytes)}
        </span>
      </span>
      {busy ? (
        <Loader2 size={16} className="animate-spin" />
      ) : (
        <Download size={16} className="shrink-0" />
      )}
    </button>
  );
}
