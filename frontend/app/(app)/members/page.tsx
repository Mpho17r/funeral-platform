"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";
import api from "@/lib/api";
import { useBranches } from "@/lib/branches";
import {
  ALL_BRANCHES,
  BranchBadge,
  BranchFilter,
  BranchSelect,
  MoveButton,
  TransferDialog,
  matchesBranch,
} from "@/components/BranchControls";
import { ContactPreferencesDialog } from "@/components/ContactPreferencesDialog";
import {
  AnonymiseMemberDialog,
  ArchiveMemberDialog,
  downloadMemberData,
} from "@/components/MemberPrivacy";
import {
  Archive,
  Download,
  Edit,
  MessageSquare,
  Plus,
  RotateCcw,
  Search,
  ShieldOff,
  Users,
  X,
} from "lucide-react";

type Member = {
  id: string;
  business_id: string;
  member_number: string;
  first_name: string;
  last_name: string;
  id_number: string | null;
  date_of_birth: string | null;
  phone: string | null;
  email: string | null;
  address: string | null;
  join_date: string;
  status: string;
  branch_id: string | null;
  archived_at: string | null;
  anonymised_at: string | null;
  created_at: string;
  updated_at: string;
};

type MemberForm = {
  member_number: string;
  first_name: string;
  last_name: string;
  id_number: string;
  date_of_birth: string;
  phone: string;
  email: string;
  address: string;
  join_date: string;
  status: string;
};

const emptyForm: MemberForm = {
  member_number: "",
  first_name: "",
  last_name: "",
  id_number: "",
  date_of_birth: "",
  phone: "",
  email: "",
  address: "",
  join_date: new Date().toISOString().split("T")[0],
  status: "active",
};

function formatDate(value: string | null) {
  if (!value) return "—";

  return new Date(`${value}T00:00:00`).toLocaleDateString("en-ZA", {
    day: "2-digit",
    month: "short",
    year: "numeric",
  });
}

function statusLabel(status: string) {
  return status.charAt(0).toUpperCase() + status.slice(1);
}

function statusClass(status: string) {
  switch (status) {
    case "active":
      return "bg-green-100 text-green-700";
    case "arrears":
      return "bg-yellow-100 text-yellow-700";
    case "lapsed":
      return "bg-red-100 text-red-700";
    case "cancelled":
      return "bg-gray-100 dark:bg-slate-800 text-gray-700 dark:text-slate-300";
    case "deceased":
      return "bg-purple-100 text-purple-700";
    default:
      return "bg-gray-100 dark:bg-slate-800 text-gray-700 dark:text-slate-300";
  }
}

function getApiErrorDetails(error: unknown): {
  status?: number;
  detail?: string;
} {
  if (error === null || typeof error !== "object") return {};

  const errorRecord = error as Record<string, unknown>;
  const response = errorRecord.response;
  if (response === null || typeof response !== "object") return {};

  const responseRecord = response as Record<string, unknown>;
  const data = responseRecord.data;
  const detail =
    data !== null && typeof data === "object"
      ? (data as Record<string, unknown>).detail
      : undefined;

  return {
    status:
      typeof responseRecord.status === "number"
        ? responseRecord.status
        : undefined,
    detail: typeof detail === "string" ? detail : undefined,
  };
}

export default function MembersPage() {
  const [members, setMembers] = useState<Member[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  const [showModal, setShowModal] = useState(false);
  const [editingMember, setEditingMember] = useState<Member | null>(null);

  const [form, setForm] = useState<MemberForm>(emptyForm);
  const [search, setSearch] = useState("");

  const [error, setError] = useState("");

  const branchData = useBranches();
  const [branchFilter, setBranchFilter] = useState(ALL_BRANCHES);
  const [newMemberBranch, setNewMemberBranch] = useState("");
  const [moving, setMoving] = useState<Member | null>(null);
  const [contactFor, setContactFor] = useState<Member | null>(null);
  const [notice, setNotice] = useState("");

  const [view, setView] = useState<"current" | "archived">("current");
  const [archiving, setArchiving] = useState<Member | null>(null);
  const [anonymising, setAnonymising] = useState<Member | null>(null);

  const loadMembers = useCallback(async () => {
    try {
      setLoading(true);
      setError("");

      const response = await api.get<Member[]>("/members", {
        params: view === "archived" ? { archived: true } : undefined,
      });
      setMembers(response.data);
    } catch (err: unknown) {
      console.error(err);
      const { status, detail } = getApiErrorDetails(err);

      if (status === 401) {
        setError("Your session has expired. Please log in again.");
      } else if (status === 403) {
        setError("You do not have permission to view members.");
      } else {
        setError(detail || "Failed to load members.");
      }
    } finally {
      setLoading(false);
    }
  }, [view]);

  useEffect(() => {
    async function initializeMembers() {
      await loadMembers();
    }

    void initializeMembers();
  }, [loadMembers]);

  function openCreateModal() {
    setEditingMember(null);
    setForm({
      ...emptyForm,
      join_date: new Date().toISOString().split("T")[0],
    });
    setNewMemberBranch("");
    setError("");
    setShowModal(true);
  }

  function openEditModal(member: Member) {
    setEditingMember(member);

    setForm({
      member_number: member.member_number,
      first_name: member.first_name,
      last_name: member.last_name,
      id_number: member.id_number || "",
      date_of_birth: member.date_of_birth || "",
      phone: member.phone || "",
      email: member.email || "",
      address: member.address || "",
      join_date: member.join_date,
      status: member.status,
    });

    setError("");
    setShowModal(true);
  }

  function closeModal() {
    if (saving) return;

    setShowModal(false);
    setEditingMember(null);
    setForm(emptyForm);
    setError("");
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    if (!form.member_number.trim()) {
      setError("Member number is required.");
      return;
    }

    if (!form.first_name.trim()) {
      setError("First name is required.");
      return;
    }

    if (!form.last_name.trim()) {
      setError("Last name is required.");
      return;
    }

    try {
      setSaving(true);
      setError("");

      const payload = {
        member_number: form.member_number.trim(),
        first_name: form.first_name.trim(),
        last_name: form.last_name.trim(),
        id_number: form.id_number.trim() || null,
        date_of_birth: form.date_of_birth || null,
        phone: form.phone.trim() || null,
        email: form.email.trim() || null,
        address: form.address.trim() || null,
        join_date: form.join_date,
        status: form.status,
      };

      if (editingMember) {
        await api.patch(
          `/members/${editingMember.id}`,
          payload
        );
      } else {
        await api.post("/members", {
          ...payload,
          // Left empty, the server uses the creator's own branch.
          ...(newMemberBranch
            ? { branch_id: newMemberBranch }
            : {}),
        });
      }

      closeModal();
      await loadMembers();
    } catch (err: unknown) {
      console.error(err);
      const { status, detail } = getApiErrorDetails(err);

      if (status === 401) {
        setError("Your session has expired. Please log in again.");
      } else if (status === 403) {
        setError("Only a Main Admin can create or edit members.");
      } else if (status === 409) {
        setError(detail || "That member number already exists.");
      } else {
        setError(detail || "Failed to save member.");
      }
    } finally {
      setSaving(false);
    }
  }

  async function handleRestore(member: Member) {
    try {
      setError("");

      await api.post(`/members/${member.id}/restore`);

      setNotice(
        `${member.first_name} ${member.last_name} was restored.`,
      );
      await loadMembers();
    } catch (err: unknown) {
      console.error(err);
      const { detail } = getApiErrorDetails(err);
      setError(detail || "Failed to restore member.");
    }
  }

  async function handleExport(member: Member) {
    try {
      setError("");

      await downloadMemberData(member);

      setNotice(
        `Downloaded everything held about ${member.member_number}. The download is recorded in the audit trail.`,
      );
    } catch (err: unknown) {
      console.error(err);
      const { detail } = getApiErrorDetails(err);
      setError(detail || "Failed to download the member's data.");
    }
  }

  const filteredMembers = members.filter((member) => {
    if (!matchesBranch(branchFilter, member.branch_id)) {
      return false;
    }

    const query = search.toLowerCase().trim();

    if (!query) return true;

    return (
      member.member_number.toLowerCase().includes(query) ||
      member.first_name.toLowerCase().includes(query) ||
      member.last_name.toLowerCase().includes(query) ||
      (member.phone || "").toLowerCase().includes(query) ||
      (member.email || "").toLowerCase().includes(query) ||
      member.status.toLowerCase().includes(query)
    );
  });

  const activeCount = members.filter(
    (member) => member.status === "active"
  ).length;

  const arrearsCount = members.filter(
    (member) => member.status === "arrears"
  ).length;

  const lapsedCount = members.filter(
    (member) => member.status === "lapsed"
  ).length;

  return (
    <main className="min-h-screen bg-slate-100 dark:bg-slate-950">
      <div className="flex min-h-screen">

        <div className="min-w-0 flex-1 p-8">
        <div className="mx-auto max-w-7xl">
          {/* Header */}
          <div className="mb-8 flex items-center justify-between">
            <div>
              <h1 className="text-3xl font-bold text-gray-900 dark:text-slate-100">
                Members
              </h1>
              <p className="mt-1 text-gray-500 dark:text-slate-400">
                Manage funeral scheme members and their details.
              </p>
            </div>

            <button
              onClick={openCreateModal}
              className="flex items-center gap-2 rounded-lg bg-gray-900 dark:bg-emerald-500 px-5 py-3 font-medium text-white dark:text-slate-950 transition hover:bg-gray-800 dark:hover:bg-emerald-400"
            >
              <Plus size={18} />
              Add Member
            </button>
          </div>

          {/* Error */}
          {error && !showModal && (
            <div className="mb-6 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
              {error}
            </div>
          )}

          {/* Summary */}
          <div className="mb-8 grid grid-cols-1 gap-5 md:grid-cols-4">
            <div className="rounded-xl border border-gray-200 dark:border-slate-700 bg-white dark:bg-slate-900 p-5 shadow-sm">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-gray-500 dark:text-slate-400">
                    Total Members
                  </p>
                  <p className="mt-2 text-3xl font-bold text-gray-900 dark:text-slate-100">
                    {members.length}
                  </p>
                </div>

                <div className="rounded-lg bg-gray-100 dark:bg-slate-800 p-3">
                  <Users size={22} className="text-gray-700 dark:text-slate-300" />
                </div>
              </div>
            </div>

            <div className="rounded-xl border border-gray-200 dark:border-slate-700 bg-white dark:bg-slate-900 p-5 shadow-sm">
              <p className="text-sm text-gray-500 dark:text-slate-400">
                Active
              </p>
              <p className="mt-2 text-3xl font-bold text-green-600">
                {activeCount}
              </p>
            </div>

            <div className="rounded-xl border border-gray-200 dark:border-slate-700 bg-white dark:bg-slate-900 p-5 shadow-sm">
              <p className="text-sm text-gray-500 dark:text-slate-400">
                In Arrears
              </p>
              <p className="mt-2 text-3xl font-bold text-yellow-600">
                {arrearsCount}
              </p>
            </div>

            <div className="rounded-xl border border-gray-200 dark:border-slate-700 bg-white dark:bg-slate-900 p-5 shadow-sm">
              <p className="text-sm text-gray-500 dark:text-slate-400">
                Lapsed
              </p>
              <p className="mt-2 text-3xl font-bold text-red-600">
                {lapsedCount}
              </p>
            </div>
          </div>

          {/* Search */}
          <div className="mb-5 flex flex-wrap items-center gap-3">
            <div className="relative w-full max-w-md">
              <Search
                size={18}
                className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400 dark:text-slate-500"
              />

              <input
                type="text"
                placeholder="Search members..."
                value={search}
                onChange={(event) =>
                  setSearch(event.target.value)
                }
                className="w-full rounded-lg border border-gray-300 dark:border-slate-700 bg-white dark:bg-slate-900 py-3 pl-10 pr-4 text-sm outline-none focus:border-gray-500 dark:focus:border-emerald-400"
              />
            </div>

            {branchData.multiple && (
              <BranchFilter
                branches={branchData.branches}
                value={branchFilter}
                onChange={setBranchFilter}
              />
            )}

            <div
              role="tablist"
              aria-label="Member list"
              className="inline-flex rounded-lg border border-gray-300 bg-white p-1 text-sm"
            >
              {(["current", "archived"] as const).map((value) => (
                <button
                  key={value}
                  role="tab"
                  aria-selected={view === value}
                  onClick={() => {
                    setNotice("");
                    setView(value);
                  }}
                  className={`rounded-md px-3 py-1.5 font-medium ${
                    view === value
                      ? "bg-gray-900 text-white"
                      : "text-gray-600 hover:bg-gray-100"
                  }`}
                >
                  {value === "current" ? "Current" : "Archived"}
                </button>
              ))}
            </div>
          </div>

          {notice && (
            <div
              role="status"
              className="mb-5 rounded-lg border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-700"
            >
              {notice}
            </div>
          )}

          {/* Members table */}
          <div className="overflow-hidden rounded-xl border border-gray-200 dark:border-slate-700 bg-white dark:bg-slate-900 shadow-sm">
            {loading ? (
              <div className="p-10 text-center text-gray-500 dark:text-slate-400">
                Loading members...
              </div>
            ) : filteredMembers.length === 0 ? (
              <div className="p-12 text-center">
                <Users
                  size={40}
                  className="mx-auto mb-4 text-gray-300 dark:text-slate-600"
                />

                <h2 className="text-lg font-semibold text-gray-900 dark:text-slate-100">
                  {members.length === 0
                    ? view === "archived"
                      ? "No archived members"
                      : "No members yet"
                    : "No members found"}
                </h2>

                <p className="mt-1 text-sm text-gray-500 dark:text-slate-400">
                  {members.length === 0
                    ? view === "archived"
                      ? "Members you archive appear here, and can be restored."
                      : "Create your first member to start building memberships."
                    : "Try a different search term."}
                </p>

                {members.length === 0 && view === "current" && (
                  <button
                    onClick={openCreateModal}
                    className="mt-5 inline-flex items-center gap-2 rounded-lg bg-gray-900 dark:bg-emerald-500 px-4 py-2.5 text-sm font-medium text-white dark:text-slate-950 hover:bg-gray-800 dark:hover:bg-emerald-400"
                  >
                    <Plus size={17} />
                    Add First Member
                  </button>
                )}
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-left">
                  <thead className="border-b border-gray-200 dark:border-slate-700 bg-gray-50 dark:bg-slate-800">
                    <tr>
                      <th className="px-6 py-4 text-xs font-semibold uppercase tracking-wide text-gray-500 dark:text-slate-400">
                        Member
                      </th>

                      <th className="px-6 py-4 text-xs font-semibold uppercase tracking-wide text-gray-500 dark:text-slate-400">
                        Member Number
                      </th>

                      <th className="px-6 py-4 text-xs font-semibold uppercase tracking-wide text-gray-500 dark:text-slate-400">
                        Contact
                      </th>

                      <th className="px-6 py-4 text-xs font-semibold uppercase tracking-wide text-gray-500 dark:text-slate-400">
                        Join Date
                      </th>

                      <th className="px-6 py-4 text-xs font-semibold uppercase tracking-wide text-gray-500 dark:text-slate-400">
                        Status
                      </th>

                      <th className="px-6 py-4 text-right text-xs font-semibold uppercase tracking-wide text-gray-500 dark:text-slate-400">
                        Actions
                      </th>
                    </tr>
                  </thead>

                  <tbody className="divide-y divide-gray-100">
                    {filteredMembers.map((member) => (
                      <tr
                        key={member.id}
                        className="transition hover:bg-gray-50 dark:hover:bg-slate-800"
                      >
                        <td className="px-6 py-4">
                          <div>
                            <p className="font-medium text-gray-900 dark:text-slate-100">
                              {member.first_name}{" "}
                              {member.last_name}
                            </p>

                            {member.id_number && (
                              <p className="mt-1 text-xs text-gray-500 dark:text-slate-400">
                                ID: {member.id_number}
                              </p>
                            )}
                          </div>
                        </td>

                        <td className="px-6 py-4 text-sm text-gray-700 dark:text-slate-300">
                          {member.member_number}

                          {branchData.multiple && (
                            <div className="mt-1.5">
                              <BranchBadge
                                branchId={member.branch_id}
                                byId={branchData.byId}
                              />
                            </div>
                          )}
                        </td>

                        <td className="px-6 py-4">
                          <div className="text-sm text-gray-700 dark:text-slate-300">
                            {member.phone || "—"}
                          </div>

                          {member.email && (
                            <div className="mt-1 text-xs text-gray-500 dark:text-slate-400">
                              {member.email}
                            </div>
                          )}
                        </td>

                        <td className="px-6 py-4 text-sm text-gray-700 dark:text-slate-300">
                          {formatDate(member.join_date)}
                        </td>

                        <td className="px-6 py-4">
                          {view === "archived" ? (
                            <span className="inline-flex rounded-full bg-slate-200 px-3 py-1 text-xs font-medium text-slate-700">
                              {member.anonymised_at
                                ? "Details removed"
                                : "Archived"}
                            </span>
                          ) : (
                            <span
                              className={`inline-flex rounded-full px-3 py-1 text-xs font-medium ${statusClass(
                                member.status
                              )}`}
                            >
                              {statusLabel(member.status)}
                            </span>
                          )}
                        </td>

                        <td className="px-6 py-4">
                          <div className="flex items-center justify-end gap-2">
                            {branchData.multiple && (
                              <MoveButton
                                onClick={() =>
                                  setMoving(member)
                                }
                              />
                            )}

                            {view === "current" && (
                              <button
                                onClick={() =>
                                  setContactFor(member)
                                }
                                className="rounded-lg p-2 text-gray-500 dark:text-slate-400 transition hover:bg-gray-100 dark:hover:bg-slate-800 hover:text-gray-900 dark:hover:text-slate-100"
                                title="Contact preferences"
                                aria-label={`Contact preferences for ${member.first_name} ${member.last_name}`}
                              >
                                <MessageSquare size={17} />
                              </button>
                            )}

                            <button
                              onClick={() => handleExport(member)}
                              className="rounded-lg p-2 text-gray-500 dark:text-slate-400 transition hover:bg-gray-100 dark:hover:bg-slate-800 hover:text-gray-900 dark:hover:text-slate-100"
                              title="Download this member's data"
                              aria-label={`Download data for ${member.first_name} ${member.last_name}`}
                            >
                              <Download size={17} />
                            </button>

                            {view === "current" ? (
                              <>
                                <button
                                  onClick={() =>
                                    openEditModal(member)
                                  }
                                  className="rounded-lg p-2 text-gray-500 dark:text-slate-400 transition hover:bg-gray-100 dark:hover:bg-slate-800 hover:text-gray-900 dark:hover:text-slate-100"
                                  title="Edit member"
                                >
                                  <Edit size={17} />
                                </button>

                                <button
                                  onClick={() =>
                                    setArchiving(member)
                                  }
                                  className="rounded-lg p-2 text-gray-500 transition hover:bg-amber-50 hover:text-amber-700"
                                  title="Archive member"
                                  aria-label={`Archive ${member.first_name} ${member.last_name}`}
                                >
                                  <Archive size={17} />
                                </button>
                              </>
                            ) : (
                              <>
                                <button
                                  onClick={() =>
                                    handleRestore(member)
                                  }
                                  className="rounded-lg p-2 text-gray-500 dark:text-slate-400 transition hover:bg-gray-100 dark:hover:bg-slate-800 hover:text-gray-900 dark:hover:text-slate-100"
                                  title="Restore member"
                                  aria-label={`Restore ${member.first_name} ${member.last_name}`}
                                >
                                  <RotateCcw size={17} />
                                </button>

                                {!member.anonymised_at && (
                                  <button
                                    onClick={() =>
                                      setAnonymising(member)
                                    }
                                    className="rounded-lg p-2 text-gray-500 transition hover:bg-red-50 hover:text-red-600"
                                    title="Remove personal details"
                                    aria-label={`Remove personal details of ${member.first_name} ${member.last_name}`}
                                  >
                                    <ShieldOff size={17} />
                                  </button>
                                )}
                              </>
                            )}
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </div>
        </div>
      </div>

      {/* Create / Edit Modal */}
      {showModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
          <div className="max-h-[90vh] w-full max-w-2xl overflow-y-auto rounded-2xl bg-white dark:bg-slate-900 shadow-xl">
            <div className="flex items-center justify-between border-b border-gray-200 dark:border-slate-700 px-6 py-5">
              <div>
                <h2 className="text-xl font-bold text-gray-900 dark:text-slate-100">
                  {editingMember
                    ? "Edit Member"
                    : "Add Member"}
                </h2>

                <p className="mt-1 text-sm text-gray-500 dark:text-slate-400">
                  {editingMember
                    ? "Update the member's information."
                    : "Create a new funeral scheme member."}
                </p>
              </div>

              <button
                onClick={closeModal}
                className="rounded-lg p-2 text-gray-400 dark:text-slate-500 hover:bg-gray-100 dark:hover:bg-slate-800 hover:text-gray-700"
              >
                <X size={20} />
              </button>
            </div>

            <form
              onSubmit={handleSubmit}
              className="p-6"
            >
              {error && (
                <div className="mb-5 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
                  {error}
                </div>
              )}

              <div className="grid grid-cols-1 gap-5 md:grid-cols-2">
                {/* Member Number */}
                <div>
                  <label className="mb-2 block text-sm font-medium text-gray-700 dark:text-slate-300">
                    Member Number *
                  </label>

                  <input
                    type="text"
                    value={form.member_number}
                    onChange={(event) =>
                      setForm({
                        ...form,
                        member_number:
                          event.target.value,
                      })
                    }
                    placeholder="MEM-0001"
                    required
                    className="w-full rounded-lg border border-gray-300 dark:border-slate-700 px-4 py-3 text-sm outline-none focus:border-gray-500 dark:focus:border-emerald-400"
                  />
                </div>

                {/* Status */}
                <div>
                  <label className="mb-2 block text-sm font-medium text-gray-700 dark:text-slate-300">
                    Status
                  </label>

                  <select
                    value={form.status}
                    onChange={(event) =>
                      setForm({
                        ...form,
                        status: event.target.value,
                      })
                    }
                    className="w-full rounded-lg border border-gray-300 dark:border-slate-700 bg-white dark:bg-slate-900 px-4 py-3 text-sm outline-none focus:border-gray-500 dark:focus:border-emerald-400"
                  >
                    <option value="active">
                      Active
                    </option>
                    <option value="arrears">
                      Arrears
                    </option>
                    <option value="lapsed">
                      Lapsed
                    </option>
                    <option value="cancelled">
                      Cancelled
                    </option>
                    <option value="deceased">
                      Deceased
                    </option>
                  </select>
                </div>

                {/* First Name */}
                <div>
                  <label className="mb-2 block text-sm font-medium text-gray-700 dark:text-slate-300">
                    First Name *
                  </label>

                  <input
                    type="text"
                    value={form.first_name}
                    onChange={(event) =>
                      setForm({
                        ...form,
                        first_name:
                          event.target.value,
                      })
                    }
                    required
                    className="w-full rounded-lg border border-gray-300 dark:border-slate-700 px-4 py-3 text-sm outline-none focus:border-gray-500 dark:focus:border-emerald-400"
                  />
                </div>

                {/* Last Name */}
                <div>
                  <label className="mb-2 block text-sm font-medium text-gray-700 dark:text-slate-300">
                    Last Name *
                  </label>

                  <input
                    type="text"
                    value={form.last_name}
                    onChange={(event) =>
                      setForm({
                        ...form,
                        last_name:
                          event.target.value,
                      })
                    }
                    required
                    className="w-full rounded-lg border border-gray-300 dark:border-slate-700 px-4 py-3 text-sm outline-none focus:border-gray-500 dark:focus:border-emerald-400"
                  />
                </div>

                {/* ID Number */}
                <div>
                  <label className="mb-2 block text-sm font-medium text-gray-700 dark:text-slate-300">
                    ID Number
                  </label>

                  <input
                    type="text"
                    value={form.id_number}
                    onChange={(event) =>
                      setForm({
                        ...form,
                        id_number:
                          event.target.value,
                      })
                    }
                    className="w-full rounded-lg border border-gray-300 dark:border-slate-700 px-4 py-3 text-sm outline-none focus:border-gray-500 dark:focus:border-emerald-400"
                  />
                </div>

                {/* Date of Birth */}
                <div>
                  <label className="mb-2 block text-sm font-medium text-gray-700 dark:text-slate-300">
                    Date of Birth
                  </label>

                  <input
                    type="date"
                    value={form.date_of_birth}
                    onChange={(event) =>
                      setForm({
                        ...form,
                        date_of_birth:
                          event.target.value,
                      })
                    }
                    className="w-full rounded-lg border border-gray-300 dark:border-slate-700 px-4 py-3 text-sm outline-none focus:border-gray-500 dark:focus:border-emerald-400"
                  />
                </div>

                {/* Phone */}
                <div>
                  <label className="mb-2 block text-sm font-medium text-gray-700 dark:text-slate-300">
                    Phone
                  </label>

                  <input
                    type="tel"
                    value={form.phone}
                    onChange={(event) =>
                      setForm({
                        ...form,
                        phone: event.target.value,
                      })
                    }
                    placeholder="082 123 4567"
                    className="w-full rounded-lg border border-gray-300 dark:border-slate-700 px-4 py-3 text-sm outline-none focus:border-gray-500 dark:focus:border-emerald-400"
                  />
                </div>

                {/* Email */}
                <div>
                  <label className="mb-2 block text-sm font-medium text-gray-700 dark:text-slate-300">
                    Email
                  </label>

                  <input
                    type="email"
                    value={form.email}
                    onChange={(event) =>
                      setForm({
                        ...form,
                        email: event.target.value,
                      })
                    }
                    placeholder="member@example.com"
                    className="w-full rounded-lg border border-gray-300 dark:border-slate-700 px-4 py-3 text-sm outline-none focus:border-gray-500 dark:focus:border-emerald-400"
                  />
                </div>

                {/* Join Date */}
                <div>
                  <label className="mb-2 block text-sm font-medium text-gray-700 dark:text-slate-300">
                    Join Date
                  </label>

                  <input
                    type="date"
                    value={form.join_date}
                    onChange={(event) =>
                      setForm({
                        ...form,
                        join_date:
                          event.target.value,
                      })
                    }
                    className="w-full rounded-lg border border-gray-300 dark:border-slate-700 px-4 py-3 text-sm outline-none focus:border-gray-500 dark:focus:border-emerald-400"
                  />
                </div>

                {/* Address */}
                <div className="md:col-span-2">
                  <label className="mb-2 block text-sm font-medium text-gray-700 dark:text-slate-300">
                    Address
                  </label>

                  <textarea
                    value={form.address}
                    onChange={(event) =>
                      setForm({
                        ...form,
                        address:
                          event.target.value,
                      })
                    }
                    rows={3}
                    className="w-full resize-none rounded-lg border border-gray-300 dark:border-slate-700 px-4 py-3 text-sm outline-none focus:border-gray-500 dark:focus:border-emerald-400"
                  />
                </div>

                {/* Branch: chosen when creating; moved later with
                    the Move action. */}
                {branchData.multiple && !editingMember && (
                  <div className="md:col-span-2">
                    <BranchSelect
                      branches={branchData.branches}
                      value={newMemberBranch}
                      onChange={setNewMemberBranch}
                    />
                  </div>
                )}
              </div>

              <div className="mt-7 flex justify-end gap-3 border-t border-gray-200 dark:border-slate-700 pt-5">
                <button
                  type="button"
                  onClick={closeModal}
                  disabled={saving}
                  className="rounded-lg border border-gray-300 dark:border-slate-700 px-5 py-2.5 text-sm font-medium text-gray-700 dark:text-slate-300 hover:bg-gray-50 dark:hover:bg-slate-800 disabled:opacity-50"
                >
                  Cancel
                </button>

                <button
                  type="submit"
                  disabled={saving}
                  className="rounded-lg bg-gray-900 dark:bg-emerald-500 px-5 py-2.5 text-sm font-medium text-white dark:text-slate-950 hover:bg-gray-800 dark:hover:bg-emerald-400 disabled:cursor-not-allowed disabled:opacity-50"
                >
                  {saving
                    ? "Saving..."
                    : editingMember
                      ? "Save Changes"
                      : "Create Member"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {moving && (
        <TransferDialog
          path={`/members/${moving.id}/transfer`}
          subject={`${moving.first_name} ${moving.last_name}`}
          currentBranchId={moving.branch_id}
          branches={branchData.branches}
          onClose={() => setMoving(null)}
          onMoved={(message) => {
            setMoving(null);
            setNotice(message);
            loadMembers();
          }}
        />
      )}

      {archiving && (
        <ArchiveMemberDialog
          member={archiving}
          onClose={() => setArchiving(null)}
          onDone={(message) => {
            setArchiving(null);
            setNotice(message);
            loadMembers();
          }}
        />
      )}

      {anonymising && (
        <AnonymiseMemberDialog
          member={anonymising}
          onClose={() => setAnonymising(null)}
          onDone={(message) => {
            setAnonymising(null);
            setNotice(message);
            loadMembers();
          }}
        />
      )}

      {contactFor && (
        <ContactPreferencesDialog
          memberId={contactFor.id}
          memberName={`${contactFor.first_name} ${contactFor.last_name}`}
          onClose={() => setContactFor(null)}
          onSaved={() => {
            setNotice(
              `Contact preferences saved for ${contactFor.first_name} ${contactFor.last_name}.`,
            );
            setContactFor(null);
          }}
        />
      )}
    </main>
  );
}
