"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import {
  Download,
  FileText,
  Pencil,
  Plus,
  RefreshCw,
  Trash2,
  Upload,
  X,
} from "lucide-react";
import api from "@/lib/api";
import { isAuthenticated } from "@/lib/auth";

type CaseDocument = {
  id: string;
  business_id: string;
  case_id: string;
  document_type: string;
  original_filename: string;
  stored_filename: string;
  file_path: string;
  mime_type: string | null;
  file_size: number | null;
  description: string | null;
  uploaded_by: string | null;
  created_at: string;
  updated_at: string;
};

type DocumentForm = {
  document_type: string;
  description: string;
};

const DOCUMENT_TYPES = [
  { value: "id_document", label: "ID Document" },
  { value: "death_certificate", label: "Death Certificate" },
  { value: "proof_of_death", label: "Proof of Death" },
  { value: "supporting_document", label: "Supporting Document" },
];

const ALLOWED_MIME_TYPES = [
  "application/pdf",
  "image/jpeg",
  "image/png",
  "image/webp",
  "text/plain",
];

const MAX_FILE_SIZE = 10 * 1024 * 1024;

const emptyForm: DocumentForm = {
  document_type: "supporting_document",
  description: "",
};

function formatDocumentType(value: string) {
  const match = DOCUMENT_TYPES.find((type) => type.value === value);

  if (match) {
    return match.label;
  }

  return value
    .replace(/_/g, " ")
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function formatFileSize(size: number | null) {
  if (size === null || size === undefined) {
    return "Unknown size";
  }

  if (size < 1024) {
    return `${size} B`;
  }

  if (size < 1024 * 1024) {
    return `${(size / 1024).toFixed(1)} KB`;
  }

  return `${(size / (1024 * 1024)).toFixed(1)} MB`;
}

function formatDate(value: string) {
  if (!value) {
    return "—";
  }

  return new Date(value).toLocaleString();
}

function getApiError(error: any, fallback: string) {
  return (
    error?.response?.data?.detail ||
    error?.response?.data?.message ||
    error?.message ||
    fallback
  );
}

export default function CaseDocumentsPage() {
  const params = useParams();
  const router = useRouter();

  const caseId = Array.isArray(params.case_id)
    ? params.case_id[0]
    : params.case_id;

  const [documents, setDocuments] = useState<CaseDocument[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const [showUploadForm, setShowUploadForm] = useState(false);
  const [editingDocument, setEditingDocument] =
    useState<CaseDocument | null>(null);

  const [form, setForm] = useState<DocumentForm>(emptyForm);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);

  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  const isValidUuid = useMemo(() => {
    if (!caseId) {
      return false;
    }

    return /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(
      caseId,
    );
  }, [caseId]);

  useEffect(() => {
    if (!isAuthenticated()) {
      router.replace("/login");
      return;
    }

    if (!isValidUuid) {
      setError("Invalid case ID.");
      setLoading(false);
      return;
    }

    loadDocuments();
  }, [isValidUuid, caseId, router]);

  async function loadDocuments(showRefreshState = false) {
    if (!caseId || !isValidUuid) {
      return;
    }

    try {
      setError("");

      if (showRefreshState) {
        setRefreshing(true);
      } else {
        setLoading(true);
      }

      const response = await api.get(`/cases/${caseId}/documents`);
      setDocuments(response.data);
    } catch (error: any) {
      if (error?.response?.status === 401) {
        localStorage.removeItem("access_token");
        router.replace("/login");
        return;
      }

      if (error?.response?.status === 403) {
        setError("You do not have permission to view case documents.");
        return;
      }

      if (error?.response?.status === 404) {
        setError("Case not found.");
        return;
      }

      setError(getApiError(error, "Failed to load documents."));
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }

  function resetUploadForm() {
    setForm(emptyForm);
    setSelectedFile(null);
    setShowUploadForm(false);
  }

  function openUploadForm() {
    setError("");
    setSuccess("");
    setEditingDocument(null);
    setForm(emptyForm);
    setSelectedFile(null);
    setShowUploadForm(true);
  }

  function openEditForm(document: CaseDocument) {
    setError("");
    setSuccess("");
    setShowUploadForm(false);
    setEditingDocument(document);

    setForm({
      document_type: document.document_type,
      description: document.description || "",
    });
  }

  async function submitUpload(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    if (!caseId) {
      return;
    }

    setError("");
    setSuccess("");

    if (!selectedFile) {
      setError("Please select a file.");
      return;
    }

    if (!ALLOWED_MIME_TYPES.includes(selectedFile.type)) {
      setError(
        "Unsupported file type. Please upload PDF, JPEG, PNG, WebP, or plain text.",
      );
      return;
    }

    if (selectedFile.size > MAX_FILE_SIZE) {
      setError("File is too large. Maximum file size is 10 MB.");
      return;
    }

    try {
      setSubmitting(true);

      const formData = new FormData();
      formData.append("document_type", form.document_type);
      formData.append("description", form.description.trim());
      formData.append("file", selectedFile);

      await api.post(`/cases/${caseId}/documents`, formData);

      setSuccess("Document uploaded successfully.");
      resetUploadForm();
      await loadDocuments();
    } catch (error: any) {
      if (error?.response?.status === 401) {
        localStorage.removeItem("access_token");
        router.replace("/login");
        return;
      }

      if (error?.response?.status === 403) {
        setError("You do not have permission to upload documents.");
        return;
      }

      setError(getApiError(error, "Failed to upload document."));
    } finally {
      setSubmitting(false);
    }
  }

  async function submitEdit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    if (!editingDocument) {
      return;
    }

    setError("");
    setSuccess("");

    try {
      setSubmitting(true);

      await api.patch(`/cases/documents/${editingDocument.id}`, {
        document_type: form.document_type,
        description: form.description.trim() || null,
      });

      setSuccess("Document updated successfully.");
      setEditingDocument(null);
      setForm(emptyForm);
      await loadDocuments();
    } catch (error: any) {
      if (error?.response?.status === 401) {
        localStorage.removeItem("access_token");
        router.replace("/login");
        return;
      }

      if (error?.response?.status === 403) {
        setError("You do not have permission to edit documents.");
        return;
      }

      setError(getApiError(error, "Failed to update document."));
    } finally {
      setSubmitting(false);
    }
  }

  async function downloadDocument(document: CaseDocument) {
    try {
      setError("");

      const response = await api.get(
        `/cases/documents/${document.id}/download`,
        {
          responseType: "blob",
        },
      );

      const blobUrl = window.URL.createObjectURL(response.data);
      const link = window.document.createElement("a");

      link.href = blobUrl;
      link.download = document.original_filename;
      window.document.body.appendChild(link);
      link.click();
      link.remove();

      window.URL.revokeObjectURL(blobUrl);
    } catch (error: any) {
      if (error?.response?.status === 401) {
        localStorage.removeItem("access_token");
        router.replace("/login");
        return;
      }

      if (error?.response?.status === 403) {
        setError("You do not have permission to download documents.");
        return;
      }

      if (error?.response?.status === 404) {
        setError("Document file could not be found.");
        return;
      }

      setError(getApiError(error, "Failed to download document."));
    }
  }

  async function deleteDocument(document: CaseDocument) {
    const confirmed = window.confirm(
      `Delete "${document.original_filename}"? This cannot be undone.`,
    );

    if (!confirmed) {
      return;
    }

    try {
      setError("");
      setSuccess("");

      await api.delete(`/cases/documents/${document.id}`);

      setSuccess("Document deleted successfully.");
      await loadDocuments();
    } catch (error: any) {
      if (error?.response?.status === 401) {
        localStorage.removeItem("access_token");
        router.replace("/login");
        return;
      }

      if (error?.response?.status === 403) {
        setError("You do not have permission to delete documents.");
        return;
      }

      if (error?.response?.status === 404) {
        setError("Document not found.");
        return;
      }

      setError(getApiError(error, "Failed to delete document."));
    }
  }

  if (loading) {
    return (
      <div className="flex min-h-[60vh] items-center justify-center">
        <div className="flex items-center gap-3 text-sm text-slate-500">
          <RefreshCw className="h-4 w-4 animate-spin" />
          Loading documents...
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
        <div>
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => router.push(`/cases/${caseId}`)}
              className="text-sm font-medium text-slate-500 hover:text-slate-900"
            >
              Case
            </button>
            <span className="text-slate-300">/</span>
            <span className="text-sm font-medium text-slate-900">
              Documents
            </span>
          </div>

          <h1 className="mt-2 text-2xl font-semibold text-slate-900">
            Case Documents
          </h1>

          <p className="mt-1 text-sm text-slate-500">
            Upload, review, download, and manage documents for this case.
          </p>
        </div>

        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            onClick={() => loadDocuments(true)}
            disabled={refreshing}
            className="inline-flex items-center gap-2 rounded-lg border border-slate-200 bg-white px-4 py-2 text-sm font-medium text-slate-700 shadow-sm hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-60"
          >
            <RefreshCw
              className={`h-4 w-4 ${refreshing ? "animate-spin" : ""}`}
            />
            Refresh
          </button>

          <button
            type="button"
            onClick={openUploadForm}
            className="inline-flex items-center gap-2 rounded-lg bg-slate-900 px-4 py-2 text-sm font-medium text-white shadow-sm hover:bg-slate-800"
          >
            <Plus className="h-4 w-4" />
            Upload Document
          </button>
        </div>
      </div>

      {error && (
        <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          {error}
        </div>
      )}

      {success && (
        <div className="rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-700">
          {success}
        </div>
      )}

      {(showUploadForm || editingDocument) && (
        <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
          <div className="mb-5 flex items-center justify-between">
            <div>
              <h2 className="text-lg font-semibold text-slate-900">
                {editingDocument ? "Edit Document" : "Upload Document"}
              </h2>

              <p className="mt-1 text-sm text-slate-500">
                {editingDocument
                  ? "Update the document category or description."
                  : "Accepted files: PDF, JPEG, PNG, WebP, or plain text. Maximum 10 MB."}
              </p>
            </div>

            <button
              type="button"
              onClick={() => {
                setShowUploadForm(false);
                setEditingDocument(null);
                setForm(emptyForm);
                setSelectedFile(null);
              }}
              className="rounded-lg p-2 text-slate-400 hover:bg-slate-100 hover:text-slate-700"
              aria-label="Close form"
            >
              <X className="h-5 w-5" />
            </button>
          </div>

          <form
            onSubmit={editingDocument ? submitEdit : submitUpload}
            className="space-y-5"
          >
            <div className="grid gap-5 md:grid-cols-2">
              <div>
                <label
                  htmlFor="document_type"
                  className="mb-2 block text-sm font-medium text-slate-700"
                >
                  Document Type
                </label>

                <select
                  id="document_type"
                  value={form.document_type}
                  onChange={(event) =>
                    setForm((current) => ({
                      ...current,
                      document_type: event.target.value,
                    }))
                  }
                  className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2.5 text-sm text-slate-900 outline-none focus:border-slate-500 focus:ring-2 focus:ring-slate-200"
                >
                  {DOCUMENT_TYPES.map((type) => (
                    <option key={type.value} value={type.value}>
                      {type.label}
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label
                  htmlFor="description"
                  className="mb-2 block text-sm font-medium text-slate-700"
                >
                  Description
                </label>

                <input
                  id="description"
                  type="text"
                  value={form.description}
                  onChange={(event) =>
                    setForm((current) => ({
                      ...current,
                      description: event.target.value,
                    }))
                  }
                  placeholder="Optional description"
                  className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2.5 text-sm text-slate-900 outline-none placeholder:text-slate-400 focus:border-slate-500 focus:ring-2 focus:ring-slate-200"
                />
              </div>
            </div>

            {!editingDocument && (
              <div>
                <label
                  htmlFor="document_file"
                  className="mb-2 block text-sm font-medium text-slate-700"
                >
                  File
                </label>

                <input
                  id="document_file"
                  type="file"
                  accept=".pdf,.jpg,.jpeg,.png,.webp,.txt"
                  onChange={(event) =>
                    setSelectedFile(event.target.files?.[0] || null)
                  }
                  className="block w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-700 file:mr-4 file:rounded-md file:border-0 file:bg-slate-100 file:px-3 file:py-2 file:text-sm file:font-medium file:text-slate-700 hover:file:bg-slate-200"
                />

                {selectedFile && (
                  <p className="mt-2 text-xs text-slate-500">
                    {selectedFile.name} · {formatFileSize(selectedFile.size)}
                  </p>
                )}
              </div>
            )}

            <div className="flex justify-end gap-2">
              <button
                type="button"
                onClick={() => {
                  setShowUploadForm(false);
                  setEditingDocument(null);
                  setForm(emptyForm);
                  setSelectedFile(null);
                }}
                className="rounded-lg border border-slate-200 bg-white px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"
              >
                Cancel
              </button>

              <button
                type="submit"
                disabled={submitting}
                className="inline-flex items-center gap-2 rounded-lg bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-60"
              >
                {editingDocument ? (
                  <Pencil className="h-4 w-4" />
                ) : (
                  <Upload className="h-4 w-4" />
                )}

                {submitting
                  ? "Saving..."
                  : editingDocument
                    ? "Save Changes"
                    : "Upload Document"}
              </button>
            </div>
          </form>
        </div>
      )}

      {documents.length === 0 ? (
        <div className="rounded-2xl border border-dashed border-slate-300 bg-white px-6 py-14 text-center">
          <FileText className="mx-auto h-10 w-10 text-slate-300" />

          <h2 className="mt-4 text-base font-semibold text-slate-900">
            No documents yet
          </h2>

          <p className="mx-auto mt-1 max-w-md text-sm text-slate-500">
            Upload important case documents such as identification,
            certificates, proof of death, and supporting records.
          </p>

          <button
            type="button"
            onClick={openUploadForm}
            className="mt-5 inline-flex items-center gap-2 rounded-lg bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-800"
          >
            <Upload className="h-4 w-4" />
            Upload First Document
          </button>
        </div>
      ) : (
        <div className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
          <div className="border-b border-slate-200 px-6 py-4">
            <h2 className="text-base font-semibold text-slate-900">
              Documents ({documents.length})
            </h2>
          </div>

          <div className="divide-y divide-slate-100">
            {documents.map((document) => (
              <div
                key={document.id}
                className="flex flex-col gap-4 px-6 py-5 lg:flex-row lg:items-center lg:justify-between"
              >
                <div className="flex min-w-0 items-start gap-4">
                  <div className="rounded-xl bg-slate-100 p-3">
                    <FileText className="h-5 w-5 text-slate-600" />
                  </div>

                  <div className="min-w-0">
                    <h3 className="truncate text-sm font-semibold text-slate-900">
                      {document.original_filename}
                    </h3>

                    <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-slate-500">
                      <span>{formatDocumentType(document.document_type)}</span>
                      <span>{formatFileSize(document.file_size)}</span>
                      <span>{formatDate(document.created_at)}</span>
                    </div>

                    {document.description && (
                      <p className="mt-2 text-sm text-slate-600">
                        {document.description}
                      </p>
                    )}
                  </div>
                </div>

                <div className="flex shrink-0 flex-wrap gap-2">
                  <button
                    type="button"
                    onClick={() => downloadDocument(document)}
                    className="inline-flex items-center gap-2 rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"
                  >
                    <Download className="h-4 w-4" />
                    Download
                  </button>

                  <button
                    type="button"
                    onClick={() => openEditForm(document)}
                    className="inline-flex items-center gap-2 rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"
                  >
                    <Pencil className="h-4 w-4" />
                    Edit
                  </button>

                  <button
                    type="button"
                    onClick={() => deleteDocument(document)}
                    className="inline-flex items-center gap-2 rounded-lg border border-red-200 bg-white px-3 py-2 text-sm font-medium text-red-600 hover:bg-red-50"
                  >
                    <Trash2 className="h-4 w-4" />
                    Delete
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
