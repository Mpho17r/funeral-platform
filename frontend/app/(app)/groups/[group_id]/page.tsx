"use client";

import { FormEvent, useEffect, useState } from "react";
import {
  AlertCircle,
  ArrowLeft,
  CheckCircle2,
  Loader2,
  Pencil,
  ShieldCheck,
  Trash2,
  UserPlus,
  UsersRound,
  X,
} from "lucide-react";

import { usePathname, useRouter } from "next/navigation";

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

type GroupMember = {
  id: string;
  group_id: string;
  user_id: string;
  is_admin: boolean;
};

type User = {
  id: string;
  first_name?: string | null;
  last_name?: string | null;
  email?: string | null;
  role?: string | null;
  is_active?: boolean;
};

export default function GroupDetailsPage() {
  const pathname = usePathname();
  const router = useRouter();

  const groupId = pathname.split("/").filter(Boolean).pop() || "";

  const [group, setGroup] = useState<Group | null>(null);
  const [members, setMembers] = useState<GroupMember[]>([]);
  const [users, setUsers] = useState<User[]>([]);

  const [loading, setLoading] = useState(true);
  const [loadingUsers, setLoadingUsers] = useState(false);
  const [error, setError] = useState("");

  const [showEdit, setShowEdit] = useState(false);
  const [showAddMember, setShowAddMember] = useState(false);

  const [saving, setSaving] = useState(false);
  const [addingMember, setAddingMember] = useState(false);
  const [removingMemberId, setRemovingMemberId] = useState("");
  const [changingAdminId, setChangingAdminId] = useState("");

  const [name, setName] = useState("");
  const [description, setDescription] = useState("");

  const [selectedUserId, setSelectedUserId] = useState("");
  const [selectedUserAdmin, setSelectedUserAdmin] = useState(false);

  const getErrorMessage = (err: any, fallback: string) => {
    return err?.response?.data?.detail || fallback;
  };

  const loadGroup = async () => {
    try {
      setLoading(true);
      setError("");

      const [groupResponse, membersResponse] = await Promise.all([
        api.get<Group>(`/groups/${groupId}`),
        api.get<GroupMember[]>(`/groups/${groupId}/members`),
      ]);

      setGroup(groupResponse.data);
      setMembers(membersResponse.data);

      setName(groupResponse.data.name);
      setDescription(groupResponse.data.description || "");
    } catch (err: any) {
      setError(getErrorMessage(err, "Unable to load this group."));
    } finally {
      setLoading(false);
    }
  };

  const loadUsers = async () => {
    try {
      setLoadingUsers(true);

      const response = await api.get<User[]>("/users");

      setUsers(response.data);
    } catch (err: any) {
      setError(getErrorMessage(err, "Unable to load users."));
    } finally {
      setLoadingUsers(false);
    }
  };

  useEffect(() => {
    console.log("GROUP DETAILS:", { groupId });

    if (groupId) {
      loadGroup();
      loadUsers();
    }
  }, [groupId]);

  const openAddMember = async () => {
    setError("");
    setSelectedUserId("");
    setSelectedUserAdmin(false);
    setShowAddMember(true);

    if (users.length === 0) {
      await loadUsers();
    }
  };

  const handleUpdateGroup = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();

    if (!name.trim()) {
      setError("Group name is required.");
      return;
    }

    try {
      setSaving(true);
      setError("");

      const response = await api.patch<Group>(`/groups/${groupId}`, {
        name: name.trim(),
        description: description.trim() || null,
      });

      setGroup(response.data);
      setShowEdit(false);
    } catch (err: any) {
      setError(getErrorMessage(err, "Unable to update the group."));
    } finally {
      setSaving(false);
    }
  };

  const handleAddMember = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();

    if (!selectedUserId) {
      setError("Please select a user.");
      return;
    }

    try {
      setAddingMember(true);
      setError("");

      const response = await api.post<GroupMember>(
        `/groups/${groupId}/members`,
        {
          user_id: selectedUserId,
          is_admin: selectedUserAdmin,
        }
      );

      setMembers((current) => [...current, response.data]);

      setSelectedUserId("");
      setSelectedUserAdmin(false);
      setShowAddMember(false);
    } catch (err: any) {
      setError(getErrorMessage(err, "Unable to add this member."));
    } finally {
      setAddingMember(false);
    }
  };

  const handleAdminChange = async (
    member: GroupMember,
    isAdmin: boolean
  ) => {
    try {
      setChangingAdminId(member.user_id);
      setError("");

      const response = await api.patch<GroupMember>(
        `/groups/${groupId}/members/${member.user_id}`,
        {
          is_admin: isAdmin,
        }
      );

      setMembers((current) =>
        current.map((item) =>
          item.user_id === member.user_id ? response.data : item
        )
      );
    } catch (err: any) {
      setError(getErrorMessage(err, "Unable to update member role."));
    } finally {
      setChangingAdminId("");
    }
  };

  const handleRemoveMember = async (member: GroupMember) => {
    const confirmed = window.confirm(
      "Remove this user from the group?"
    );

    if (!confirmed) {
      return;
    }

    try {
      setRemovingMemberId(member.user_id);
      setError("");

      await api.delete(
        `/groups/${groupId}/members/${member.user_id}`
      );

      setMembers((current) =>
        current.filter((item) => item.user_id !== member.user_id)
      );
    } catch (err: any) {
      setError(getErrorMessage(err, "Unable to remove this member."));
    } finally {
      setRemovingMemberId("");
    }
  };

  const handleDeleteGroup = async () => {
    const confirmed = window.confirm(
      `Delete "${group?.name}"? This will remove the group and its membership records.`
    );

    if (!confirmed) {
      return;
    }

    try {
      setSaving(true);
      setError("");

      await api.delete(`/groups/${groupId}`);

      router.push("/groups");
    } catch (err: any) {
      setError(getErrorMessage(err, "Unable to delete the group."));
      setSaving(false);
    }
  };

  const getUser = (userId: string) => {
    return users.find((user) => user.id === userId);
  };

  const getUserName = (userId: string) => {
    const user = getUser(userId);

    if (!user) {
      return "User";
    }

    const fullName = [user.first_name, user.last_name]
      .filter(Boolean)
      .join(" ")
      .trim();

    return fullName || user.email || "User";
  };

  const getUserEmail = (userId: string) => {
    const user = getUser(userId);

    return user?.email || "";
  };

  const availableUsers = users.filter(
    (user) =>
      user.is_active !== false &&
      !members.some((member) => member.user_id === user.id)
  );

  if (loading) {
    return (
      <div className="flex min-h-[400px] items-center justify-center">
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          <Loader2 className="h-5 w-5 animate-spin" />
          Loading group...
        </div>
      </div>
    );
  }

  if (!group) {
    return (
      <div className="space-y-6">
        <button
          type="button"
          onClick={() => router.push("/groups")}
          className="inline-flex items-center gap-2 text-sm font-medium text-muted-foreground transition hover:text-foreground"
        >
          <ArrowLeft className="h-4 w-4" />
          Back to Groups
        </button>

        <div className="rounded-xl border border-red-200 bg-red-50 p-6 text-sm text-red-700 dark:border-red-900/50 dark:bg-red-950/30 dark:text-red-300">
          {error || "Group not found."}
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col gap-4">
        <button
          type="button"
          onClick={() => router.push("/groups")}
          className="inline-flex w-fit items-center gap-2 text-sm font-medium text-muted-foreground transition hover:text-foreground"
        >
          <ArrowLeft className="h-4 w-4" />
          Back to Groups
        </button>

        <div className="flex flex-col gap-4 rounded-xl border bg-card p-6 lg:flex-row lg:items-start lg:justify-between">
          <div className="flex gap-4">
            <div className="flex h-14 w-14 shrink-0 items-center justify-center rounded-xl bg-primary/10">
              <UsersRound className="h-7 w-7 text-primary" />
            </div>

            <div>
              <h1 className="text-2xl font-semibold tracking-tight">
                {group.name}
              </h1>

              <p className="mt-1 max-w-2xl text-sm text-muted-foreground">
                {group.description || "No description provided."}
              </p>

              <div className="mt-3 flex items-center gap-2 text-xs text-muted-foreground">
                <UsersRound className="h-3.5 w-3.5" />
                {members.length}{" "}
                {members.length === 1 ? "member" : "members"}
              </div>
            </div>
          </div>

          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              onClick={() => {
                setError("");
                setShowEdit(true);
              }}
              className="inline-flex items-center gap-2 rounded-lg border px-3 py-2 text-sm font-medium transition hover:bg-muted"
            >
              <Pencil className="h-4 w-4" />
              Edit Group
            </button>

            <button
              type="button"
              onClick={handleDeleteGroup}
              disabled={saving}
              className="inline-flex items-center gap-2 rounded-lg border border-red-200 px-3 py-2 text-sm font-medium text-red-600 transition hover:bg-red-50 disabled:cursor-not-allowed disabled:opacity-60 dark:border-red-900/50 dark:text-red-400 dark:hover:bg-red-950/30"
            >
              {saving ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Trash2 className="h-4 w-4" />
              )}
              Delete
            </button>
          </div>
        </div>
      </div>

      {/* Error */}
      {error && (
        <div className="flex items-start gap-3 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700 dark:border-red-900/50 dark:bg-red-950/30 dark:text-red-300">
          <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {/* Members */}
      <section className="rounded-xl border bg-card">
        <div className="flex flex-col gap-3 border-b px-6 py-5 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h2 className="text-lg font-semibold">Members</h2>
            <p className="text-sm text-muted-foreground">
              Manage the staff members belonging to this group.
            </p>
          </div>

          <button
            type="button"
            onClick={openAddMember}
            className="inline-flex items-center justify-center gap-2 rounded-lg bg-primary px-4 py-2.5 text-sm font-medium text-primary-foreground transition hover:opacity-90"
          >
            <UserPlus className="h-4 w-4" />
            Add Member
          </button>
        </div>

        {members.length === 0 ? (
          <div className="flex min-h-[180px] flex-col items-center justify-center px-6 text-center">
            <UsersRound className="h-8 w-8 text-muted-foreground" />

            <p className="mt-3 font-medium">No members yet</p>

            <p className="mt-1 text-sm text-muted-foreground">
              Add staff members to this group.
            </p>
          </div>
        ) : (
          <div className="divide-y">
            {members.map((member) => {
              const user = getUser(member.user_id);
              const isChanging = changingAdminId === member.user_id;
              const isRemoving = removingMemberId === member.user_id;

              return (
                <div
                  key={member.id}
                  className="flex flex-col gap-4 px-6 py-4 sm:flex-row sm:items-center sm:justify-between"
                >
                  <div className="flex min-w-0 items-center gap-3">
                    <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-muted text-sm font-semibold">
                      {getUserName(member.user_id)
                        .charAt(0)
                        .toUpperCase()}
                    </div>

                    <div className="min-w-0">
                      <p className="truncate font-medium">
                        {getUserName(member.user_id)}
                      </p>

                      {getUserEmail(member.user_id) && (
                        <p className="truncate text-sm text-muted-foreground">
                          {getUserEmail(member.user_id)}
                        </p>
                      )}

                      {user?.role && (
                        <p className="mt-0.5 text-xs capitalize text-muted-foreground">
                          {user.role.replaceAll("_", " ")}
                        </p>
                      )}
                    </div>
                  </div>

                  <div className="flex flex-wrap items-center gap-2">
                    {member.is_admin ? (
                      <span className="inline-flex items-center gap-1.5 rounded-full bg-primary/10 px-2.5 py-1 text-xs font-medium text-primary">
                        <ShieldCheck className="h-3.5 w-3.5" />
                        Administrator
                      </span>
                    ) : (
                      <span className="rounded-full bg-muted px-2.5 py-1 text-xs font-medium text-muted-foreground">
                        Member
                      </span>
                    )}

                    <button
                      type="button"
                      onClick={() =>
                        handleAdminChange(member, !member.is_admin)
                      }
                      disabled={isChanging}
                      className="rounded-lg border px-3 py-2 text-xs font-medium transition hover:bg-muted disabled:cursor-not-allowed disabled:opacity-60"
                    >
                      {isChanging ? (
                        <Loader2 className="h-3.5 w-3.5 animate-spin" />
                      ) : member.is_admin ? (
                        "Remove Admin"
                      ) : (
                        "Make Admin"
                      )}
                    </button>

                    <button
                      type="button"
                      onClick={() => handleRemoveMember(member)}
                      disabled={isRemoving}
                      className="rounded-lg border border-red-200 p-2 text-red-600 transition hover:bg-red-50 disabled:cursor-not-allowed disabled:opacity-60 dark:border-red-900/50 dark:text-red-400 dark:hover:bg-red-950/30"
                      aria-label="Remove member"
                    >
                      {isRemoving ? (
                        <Loader2 className="h-4 w-4 animate-spin" />
                      ) : (
                        <Trash2 className="h-4 w-4" />
                      )}
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </section>

      {/* Group information */}
      <section className="rounded-xl border bg-card p-6">
        <div className="flex items-start gap-3">
          <CheckCircle2 className="mt-0.5 h-5 w-5 text-primary" />

          <div>
            <h2 className="font-semibold">Group information</h2>

            <p className="mt-1 text-sm text-muted-foreground">
              This group is isolated to its funeral business. Membership
              changes and administrative actions are controlled by the
              backend permission system.
            </p>
          </div>
        </div>
      </section>

      {/* Edit modal */}
      {showEdit && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 px-4">
          <div className="w-full max-w-lg rounded-xl border bg-background shadow-xl">
            <div className="flex items-center justify-between border-b px-6 py-4">
              <div>
                <h2 className="text-lg font-semibold">Edit Group</h2>
                <p className="text-sm text-muted-foreground">
                  Update the group name or description.
                </p>
              </div>

              <button
                type="button"
                onClick={() => {
                  if (!saving) {
                    setShowEdit(false);
                  }
                }}
                className="rounded-lg p-2 text-muted-foreground transition hover:bg-muted hover:text-foreground"
                aria-label="Close"
              >
                <X className="h-5 w-5" />
              </button>
            </div>

            <form onSubmit={handleUpdateGroup}>
              <div className="space-y-5 px-6 py-5">
                <div>
                  <label
                    htmlFor="edit-group-name"
                    className="mb-2 block text-sm font-medium"
                  >
                    Group name
                  </label>

                  <input
                    id="edit-group-name"
                    type="text"
                    value={name}
                    onChange={(event) => setName(event.target.value)}
                    maxLength={150}
                    disabled={saving}
                    className="w-full rounded-lg border bg-background px-3 py-2.5 text-sm outline-none transition focus:border-primary focus:ring-2 focus:ring-primary/20 disabled:opacity-60"
                  />
                </div>

                <div>
                  <label
                    htmlFor="edit-group-description"
                    className="mb-2 block text-sm font-medium"
                  >
                    Description
                  </label>

                  <textarea
                    id="edit-group-description"
                    value={description}
                    onChange={(event) =>
                      setDescription(event.target.value)
                    }
                    rows={4}
                    disabled={saving}
                    className="w-full resize-none rounded-lg border bg-background px-3 py-2.5 text-sm outline-none transition focus:border-primary focus:ring-2 focus:ring-primary/20 disabled:opacity-60"
                  />
                </div>
              </div>

              <div className="flex justify-end gap-3 border-t px-6 py-4">
                <button
                  type="button"
                  onClick={() => setShowEdit(false)}
                  disabled={saving}
                  className="rounded-lg border px-4 py-2.5 text-sm font-medium transition hover:bg-muted disabled:opacity-60"
                >
                  Cancel
                </button>

                <button
                  type="submit"
                  disabled={saving || !name.trim()}
                  className="inline-flex items-center gap-2 rounded-lg bg-primary px-4 py-2.5 text-sm font-medium text-primary-foreground transition hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-60"
                >
                  {saving && (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  )}
                  {saving ? "Saving..." : "Save Changes"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Add member modal */}
      {showAddMember && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 px-4">
          <div className="w-full max-w-lg rounded-xl border bg-background shadow-xl">
            <div className="flex items-center justify-between border-b px-6 py-4">
              <div>
                <h2 className="text-lg font-semibold">Add Member</h2>
                <p className="text-sm text-muted-foreground">
                  Add an active staff user to this group.
                </p>
              </div>

              <button
                type="button"
                onClick={() => {
                  if (!addingMember) {
                    setShowAddMember(false);
                  }
                }}
                className="rounded-lg p-2 text-muted-foreground transition hover:bg-muted hover:text-foreground"
                aria-label="Close"
              >
                <X className="h-5 w-5" />
              </button>
            </div>

            <form onSubmit={handleAddMember}>
              <div className="space-y-5 px-6 py-5">
                {loadingUsers ? (
                  <div className="flex items-center justify-center py-8 text-sm text-muted-foreground">
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    Loading users...
                  </div>
                ) : availableUsers.length === 0 ? (
                  <div className="rounded-lg border bg-muted/40 p-4 text-sm text-muted-foreground">
                    There are no available active users to add to this
                    group.
                  </div>
                ) : (
                  <>
                    <div>
                      <label
                        htmlFor="group-member"
                        className="mb-2 block text-sm font-medium"
                      >
                        User
                      </label>

                      <select
                        id="group-member"
                        value={selectedUserId}
                        onChange={(event) =>
                          setSelectedUserId(event.target.value)
                        }
                        disabled={addingMember}
                        className="w-full rounded-lg border bg-background px-3 py-2.5 text-sm outline-none transition focus:border-primary focus:ring-2 focus:ring-primary/20 disabled:opacity-60"
                      >
                        <option value="">Select a user...</option>

                        {availableUsers.map((user) => {
                          const fullName = [
                            user.first_name,
                            user.last_name,
                          ]
                            .filter(Boolean)
                            .join(" ")
                            .trim();

                          return (
                            <option key={user.id} value={user.id}>
                              {fullName || user.email || "User"}
                              {user.email ? ` — ${user.email}` : ""}
                            </option>
                          );
                        })}
                      </select>
                    </div>

                    <label className="flex cursor-pointer items-start gap-3 rounded-lg border p-4">
                      <input
                        type="checkbox"
                        checked={selectedUserAdmin}
                        onChange={(event) =>
                          setSelectedUserAdmin(event.target.checked)
                        }
                        disabled={addingMember}
                        className="mt-0.5 h-4 w-4 rounded"
                      />

                      <span>
                        <span className="block text-sm font-medium">
                          Group administrator
                        </span>
                        <span className="mt-1 block text-xs text-muted-foreground">
                          Administrators can manage members of this group
                          when their account has the required permission.
                        </span>
                      </span>
                    </label>
                  </>
                )}
              </div>

              <div className="flex justify-end gap-3 border-t px-6 py-4">
                <button
                  type="button"
                  onClick={() => setShowAddMember(false)}
                  disabled={addingMember}
                  className="rounded-lg border px-4 py-2.5 text-sm font-medium transition hover:bg-muted disabled:opacity-60"
                >
                  Cancel
                </button>

                <button
                  type="submit"
                  disabled={
                    addingMember ||
                    loadingUsers ||
                    !selectedUserId ||
                    availableUsers.length === 0
                  }
                  className="inline-flex items-center gap-2 rounded-lg bg-primary px-4 py-2.5 text-sm font-medium text-primary-foreground transition hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-60"
                >
                  {addingMember && (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  )}
                  {addingMember ? "Adding..." : "Add Member"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
