"use client";

import { FormEvent, useEffect, useState } from "react";

import {
  AlertCircle,
  CalendarDays,
  Loader2,
  Plus,
  UsersRound,
  X,
} from "lucide-react";

import { useRouter } from "next/navigation";

import api from "@/lib/api";

type Group = {
  id: string;
  business_id: string;
  name: string;
  description: string | null;
  created_by: string | null;
  created_at: string;
  updated_at: string;
};

export default function GroupsPage() {
  const router = useRouter();

  const [groups, setGroups] = useState<Group[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const [showCreateModal, setShowCreateModal] = useState(false);
  const [creating, setCreating] = useState(false);

  const [name, setName] = useState("");
  const [description, setDescription] = useState("");

  useEffect(() => {
    loadGroups();
  }, []);

  async function loadGroups() {
    try {
      setLoading(true);
      setError("");

      const response = await api.get<Group[]>("/groups");
      setGroups(response.data);
    } catch (err: any) {
      console.error("Failed to load groups:", err);

      const message =
        err?.response?.data?.detail ||
        "Unable to load groups. Please try again.";

      setError(message);
    } finally {
      setLoading(false);
    }
  }

  function openCreateModal() {
    setName("");
    setDescription("");
    setError("");
    setShowCreateModal(true);
  }

  function closeCreateModal() {
    if (creating) {
      return;
    }

    setShowCreateModal(false);
    setName("");
    setDescription("");
  }

  async function handleCreateGroup(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    const trimmedName = name.trim();
    const trimmedDescription = description.trim();

    if (!trimmedName) {
      setError("Group name is required.");
      return;
    }

    try {
      setCreating(true);
      setError("");

      const response = await api.post<Group>("/groups", {
        name: trimmedName,
        description: trimmedDescription || null,
      });

      setGroups((current) => [...current, response.data]);

      setShowCreateModal(false);
      setName("");
      setDescription("");

      router.push(`/groups/${response.data.id}`);
    } catch (err: any) {
      console.error("Failed to create group:", err);

      const message =
        err?.response?.data?.detail ||
        "Unable to create the group. Please try again.";

      setError(message);
    } finally {
      setCreating(false);
    }
  }

  function formatDate(value: string) {
    const date = new Date(value);

    if (Number.isNaN(date.getTime())) {
      return "Unknown date";
    }

    return date.toLocaleDateString("en-ZA", {
      day: "numeric",
      month: "short",
      year: "numeric",
    });
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <div className="flex items-center gap-3">
            <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-primary/10 text-primary">
              <UsersRound className="h-6 w-6" />
            </div>

            <div>
              <h1 className="text-2xl font-semibold tracking-tight">
                Groups
              </h1>

              <p className="text-sm text-muted-foreground">
                Organise staff into work groups for coordination and
                collaboration.
              </p>
            </div>
          </div>
        </div>

        <button
          type="button"
          onClick={openCreateModal}
          className="inline-flex items-center justify-center gap-2 rounded-lg bg-primary px-4 py-2.5 text-sm font-medium text-primary-foreground shadow-sm transition hover:opacity-90"
        >
          <Plus className="h-4 w-4" />
          Create Group
        </button>
      </div>

      {/* Error */}
      {error && !showCreateModal && (
        <div className="flex items-start gap-3 rounded-lg border border-destructive/30 bg-destructive/5 px-4 py-3 text-sm text-destructive">
          <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />

          <div className="flex-1">
            <p>{error}</p>
          </div>

          <button
            type="button"
            onClick={loadGroups}
            className="font-medium underline underline-offset-2"
          >
            Retry
          </button>
        </div>
      )}

      {/* Loading */}
      {loading ? (
        <div className="flex min-h-[300px] items-center justify-center rounded-xl border bg-card">
          <div className="flex items-center gap-3 text-sm text-muted-foreground">
            <Loader2 className="h-5 w-5 animate-spin" />
            Loading groups...
          </div>
        </div>
      ) : groups.length === 0 ? (
        /* Empty state */
        <div className="flex min-h-[360px] flex-col items-center justify-center rounded-xl border bg-card px-6 text-center">
          <div className="mb-4 flex h-14 w-14 items-center justify-center rounded-full bg-primary/10 text-primary">
            <UsersRound className="h-7 w-7" />
          </div>

          <h2 className="text-lg font-semibold">No groups yet</h2>

          <p className="mt-2 max-w-md text-sm text-muted-foreground">
            Create your first staff group to organise people around funeral
            operations, case coordination, or other work activities.
          </p>

          <button
            type="button"
            onClick={openCreateModal}
            className="mt-5 inline-flex items-center gap-2 rounded-lg bg-primary px-4 py-2.5 text-sm font-medium text-primary-foreground transition hover:opacity-90"
          >
            <Plus className="h-4 w-4" />
            Create Group
          </button>
        </div>
      ) : (
        /* Groups */
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {groups.map((group) => (
            <button
              key={group.id}
              type="button"
              onClick={() => router.push(`/groups/${group.id}`)}
              className="group rounded-xl border bg-card p-5 text-left shadow-sm transition hover:-translate-y-0.5 hover:shadow-md"
            >
              <div className="flex items-start justify-between gap-4">
                <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-primary/10 text-primary transition group-hover:bg-primary group-hover:text-primary-foreground">
                  <UsersRound className="h-5 w-5" />
                </div>

                <span className="text-xs text-muted-foreground">
                  Group
                </span>
              </div>

              <div className="mt-5">
                <h2 className="text-lg font-semibold">{group.name}</h2>

                <p className="mt-2 min-h-[42px] text-sm leading-6 text-muted-foreground">
                  {group.description || "No description provided."}
                </p>
              </div>

              <div className="mt-5 flex items-center gap-2 border-t pt-4 text-xs text-muted-foreground">
                <CalendarDays className="h-3.5 w-3.5" />
                Created {formatDate(group.created_at)}
              </div>
            </button>
          ))}
        </div>
      )}

      {/* Create Group Modal */}
      {showCreateModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 px-4">
          <div className="w-full max-w-lg rounded-xl border bg-background shadow-xl">
            <div className="flex items-center justify-between border-b px-6 py-4">
              <div>
                <h2 className="text-lg font-semibold">Create Group</h2>
                <p className="mt-1 text-sm text-muted-foreground">
                  Create a staff group for your workspace.
                </p>
              </div>

              <button
                type="button"
                onClick={closeCreateModal}
                disabled={creating}
                className="rounded-lg p-2 text-muted-foreground transition hover:bg-muted hover:text-foreground disabled:opacity-50"
                aria-label="Close"
              >
                <X className="h-5 w-5" />
              </button>
            </div>

            <form onSubmit={handleCreateGroup}>
              <div className="space-y-5 px-6 py-5">
                {error && (
                  <div className="flex items-start gap-3 rounded-lg border border-destructive/30 bg-destructive/5 px-4 py-3 text-sm text-destructive">
                    <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
                    <span>{error}</span>
                  </div>
                )}

                <div>
                  <label
                    htmlFor="group-name"
                    className="mb-2 block text-sm font-medium"
                  >
                    Group name
                  </label>

                  <input
                    id="group-name"
                    type="text"
                    value={name}
                    onChange={(event) => setName(event.target.value)}
                    placeholder="e.g. Operations Team"
                    maxLength={150}
                    autoFocus
                    disabled={creating}
                    className="w-full rounded-lg border bg-background px-3 py-2.5 text-sm outline-none transition focus:border-primary focus:ring-2 focus:ring-primary/20 disabled:opacity-50"
                  />
                </div>

                <div>
                  <label
                    htmlFor="group-description"
                    className="mb-2 block text-sm font-medium"
                  >
                    Description
                    <span className="ml-1 font-normal text-muted-foreground">
                      (optional)
                    </span>
                  </label>

                  <textarea
                    id="group-description"
                    value={description}
                    onChange={(event) => setDescription(event.target.value)}
                    placeholder="What is this group responsible for?"
                    rows={4}
                    disabled={creating}
                    className="w-full resize-none rounded-lg border bg-background px-3 py-2.5 text-sm outline-none transition focus:border-primary focus:ring-2 focus:ring-primary/20 disabled:opacity-50"
                  />
                </div>
              </div>

              <div className="flex items-center justify-end gap-3 border-t px-6 py-4">
                <button
                  type="button"
                  onClick={closeCreateModal}
                  disabled={creating}
                  className="rounded-lg border px-4 py-2.5 text-sm font-medium transition hover:bg-muted disabled:opacity-50"
                >
                  Cancel
                </button>

                <button
                  type="submit"
                  disabled={creating || !name.trim()}
                  className="inline-flex items-center gap-2 rounded-lg bg-primary px-4 py-2.5 text-sm font-medium text-primary-foreground transition hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-50"
                >
                  {creating && (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  )}

                  {creating ? "Creating..." : "Create Group"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
