"use client";

import { FormEvent, useEffect, useState } from "react";

import {
  ArrowLeft,
  CheckCircle2,
  Edit3,
  Plus,
  UserCheck,
  UserX,
  Users,
  X,
  XCircle,
} from "lucide-react";

import { useRouter } from "next/navigation";

import api from "@/lib/api";

type User = {
  id: string;
  business_id: string;
  full_name: string;
  email: string;
  role: string;
  is_active: boolean;
};

type UserForm = {
  full_name: string;
  email: string;
  password: string;
  role: string;
  is_active: boolean;
};

const emptyForm: UserForm = {
  full_name: "",
  email: "",
  password: "",
  role: "staff",
  is_active: true,
};

export default function TeamPage() {
  const router = useRouter();

  const [users, setUsers] = useState<User[]>([]);
  const [currentUser, setCurrentUser] = useState<User | null>(null);

  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  const [error, setError] = useState("");
  const [formError, setFormError] = useState("");

  const [showForm, setShowForm] = useState(false);
  const [editingUser, setEditingUser] = useState<User | null>(null);

  const [form, setForm] = useState<UserForm>(emptyForm);

  async function loadUsers() {
    try {
      setLoading(true);
      setError("");

      const response = await api.get<User[]>("/users");

      setUsers(response.data);

      const token = localStorage.getItem("access_token");

      if (token) {
        try {
          const payload = JSON.parse(atob(token.split(".")[1]));

          const loggedInUser = response.data.find(
            (user) => user.id === payload.sub
          );

          setCurrentUser(loggedInUser || null);
        } catch {
          setCurrentUser(null);
        }
      }
    } catch (err: any) {
      console.error("Failed to load users:", err);

      if (err.response?.status === 401) {
        setError("Your session has expired. Please log in again.");
      } else if (err.response?.status === 403) {
        setError(
          "You do not have permission to manage team members."
        );
      } else {
        setError(
          err.response?.data?.detail ||
            "Unable to load team members."
        );
      }
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadUsers();
  }, []);

  function openCreateForm() {
    setEditingUser(null);
    setForm(emptyForm);
    setFormError("");
    setShowForm(true);
  }

  function openEditForm(user: User) {
    setEditingUser(user);

    setForm({
      full_name: user.full_name,
      email: user.email,
      password: "",
      role: user.role,
      is_active: user.is_active,
    });

    setFormError("");
    setShowForm(true);
  }

  function closeForm() {
    if (saving) {
      return;
    }

    setShowForm(false);
    setEditingUser(null);
    setForm(emptyForm);
    setFormError("");
  }

  function canManageTarget(user: User) {
    if (!currentUser) {
      return false;
    }

    if (user.id === currentUser.id) {
      return false;
    }

    if (currentUser.role === "main_admin") {
      return user.role !== "main_admin";
    }

    if (currentUser.role === "manager") {
      return user.role === "staff";
    }

    return false;
  }

  function canCreateRole(role: string) {
    if (!currentUser) {
      return false;
    }

    if (currentUser.role === "main_admin") {
      return role === "manager" || role === "staff";
    }

    if (currentUser.role === "manager") {
      return role === "staff";
    }

    return false;
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setFormError("");

    const fullName = form.full_name.trim();
    const email = form.email.trim();

    if (!fullName) {
      setFormError("Full name is required.");
      return;
    }

    if (!email) {
      setFormError("Email address is required.");
      return;
    }

    if (!editingUser && !form.password) {
      setFormError("Password is required when creating a user.");
      return;
    }

    if (!editingUser && !canCreateRole(form.role)) {
      setFormError(
        "You do not have permission to create this role."
      );
      return;
    }

    if (editingUser && !canManageTarget(editingUser)) {
      setFormError(
        "You do not have permission to manage this user."
      );
      return;
    }

    try {
      setSaving(true);

      if (editingUser) {
        const payload: {
          full_name?: string;
          role?: string;
          is_active?: boolean;
        } = {
          full_name: fullName,
          role: form.role,
          is_active: form.is_active,
        };

        const response = await api.patch<User>(
          `/users/${editingUser.id}`,
          payload
        );

        setUsers((current) =>
          current.map((user) =>
            user.id === editingUser.id ? response.data : user
          )
        );
      } else {
        const response = await api.post<User>("/users", {
          full_name: fullName,
          email,
          password: form.password,
          role: form.role,
        });

        setUsers((current) => [...current, response.data]);
      }

      closeForm();
    } catch (err: any) {
      console.error("Failed to save user:", err);

      if (err.response?.status === 401) {
        setFormError("Your session has expired. Please log in again.");
      } else if (err.response?.status === 403) {
        setFormError(
          err.response?.data?.detail ||
            "You do not have permission to perform this action."
        );
      } else if (err.response?.status === 409) {
        setFormError(
          err.response?.data?.detail ||
            "That email address is already registered."
        );
      } else {
        setFormError(
          err.response?.data?.detail ||
            "Unable to save team member."
        );
      }
    } finally {
      setSaving(false);
    }
  }

  async function toggleUser(user: User) {
    if (!canManageTarget(user)) {
      return;
    }

    const action = user.is_active ? "deactivate" : "activate";

    const confirmed = window.confirm(
      `${action === "deactivate" ? "Deactivate" : "Activate"} "${user.full_name}"?`
    );

    if (!confirmed) {
      return;
    }

    try {
      if (user.is_active) {
        await api.delete(`/users/${user.id}`);

        setUsers((current) =>
          current.map((item) =>
            item.id === user.id
              ? { ...item, is_active: false }
              : item
          )
        );
      } else {
        const response = await api.patch<User>(
          `/users/${user.id}`,
          {
            is_active: true,
          }
        );

        setUsers((current) =>
          current.map((item) =>
            item.id === user.id ? response.data : item
          )
        );
      }
    } catch (err: any) {
      console.error("Failed to update user status:", err);

      setError(
        err.response?.data?.detail ||
          "Unable to update team member status."
      );
    }
  }

  const activeUsers = users.filter((user) => user.is_active);
  const inactiveUsers = users.filter((user) => !user.is_active);
  const managers = users.filter((user) => user.role === "manager");
  const staff = users.filter((user) => user.role === "staff");

  return (
    <main className="min-h-screen bg-slate-100 text-slate-900">
      <div className="flex min-w-0 flex-1 flex-col">
        <header className="border-b border-slate-200 bg-white">
          <div className="flex items-center justify-between px-6 py-5">
            <div>
              <h1 className="text-2xl font-bold text-slate-900">
                Team & Users
              </h1>
              <p className="mt-1 text-sm text-slate-500">
                Manage staff accounts, roles and access to your funeral business.
              </p>
            </div>

            <button
              type="button"
              onClick={openCreateForm}
              disabled={!currentUser || currentUser.role === "staff"}
              className="flex items-center gap-2 rounded-lg bg-slate-950 px-4 py-2.5 text-sm font-medium text-white transition hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-50"
            >
              <Plus size={18} />
              Add Team Member
            </button>
          </div>
        </header>

        <section className="flex-1 p-6 md:p-8">
          <div className="mx-auto max-w-6xl">
            <button
              type="button"
              onClick={() => router.push("/settings")}
              className="mb-6 flex items-center gap-2 text-sm font-medium text-slate-500 transition hover:text-slate-900"
            >
              <ArrowLeft size={16} />
              Back to Settings
            </button>

            {error && (
              <div className="mb-6 flex items-start gap-3 rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700">
                <XCircle size={20} className="mt-0.5 shrink-0" />

                <div className="flex-1">{error}</div>

                <button
                  type="button"
                  onClick={() => setError("")}
                  className="text-red-500 hover:text-red-700"
                >
                  <X size={18} />
                </button>
              </div>
            )}

            <div className="mb-6 grid gap-4 md:grid-cols-4">
              <div className="rounded-xl bg-white p-5 ring-1 ring-slate-200">
                <p className="text-sm text-slate-500">Total Users</p>
                <p className="mt-2 text-2xl font-bold text-slate-900">
                  {users.length}
                </p>
              </div>

              <div className="rounded-xl bg-white p-5 ring-1 ring-slate-200">
                <p className="text-sm text-slate-500">Active</p>
                <p className="mt-2 text-2xl font-bold text-slate-900">
                  {activeUsers.length}
                </p>
              </div>

              <div className="rounded-xl bg-white p-5 ring-1 ring-slate-200">
                <p className="text-sm text-slate-500">Managers</p>
                <p className="mt-2 text-2xl font-bold text-slate-900">
                  {managers.length}
                </p>
              </div>

              <div className="rounded-xl bg-white p-5 ring-1 ring-slate-200">
                <p className="text-sm text-slate-500">Staff</p>
                <p className="mt-2 text-2xl font-bold text-slate-900">
                  {staff.length}
                </p>
              </div>
            </div>

            <div className="overflow-hidden rounded-xl bg-white ring-1 ring-slate-200">
              <div className="border-b border-slate-200 px-6 py-4">
                <div className="flex items-center gap-3">
                  <Users size={20} className="text-slate-500" />

                  <div>
                    <h2 className="font-semibold text-slate-900">
                      Business Team
                    </h2>

                    <p className="text-xs text-slate-500">
                      {inactiveUsers.length} inactive account
                      {inactiveUsers.length === 1 ? "" : "s"}
                    </p>
                  </div>
                </div>
              </div>

              {loading ? (
                <div className="p-10 text-center text-sm text-slate-500">
                  Loading team members...
                </div>
              ) : users.length === 0 ? (
                <div className="p-12 text-center">
                  <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-slate-100">
                    <Users size={22} className="text-slate-500" />
                  </div>

                  <h3 className="mt-4 font-semibold text-slate-900">
                    No team members yet
                  </h3>

                  <p className="mt-2 text-sm text-slate-500">
                    Add your first staff member to start building your team.
                  </p>
                </div>
              ) : (
                <div className="divide-y divide-slate-200">
                  {users.map((user) => {
                    const isCurrentUser =
                      currentUser?.id === user.id;

                    const manageable =
                      canManageTarget(user);

                    return (
                      <div
                        key={user.id}
                        className="flex flex-col gap-4 px-6 py-5 md:flex-row md:items-center md:justify-between"
                      >
                        <div className="flex min-w-0 items-center gap-4">
                          <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-full bg-slate-100 font-semibold text-slate-700">
                            {user.full_name
                              .split(" ")
                              .map((part) => part[0])
                              .slice(0, 2)
                              .join("")
                              .toUpperCase()}
                          </div>

                          <div className="min-w-0">
                            <div className="flex flex-wrap items-center gap-2">
                              <p className="font-semibold text-slate-900">
                                {user.full_name}
                              </p>

                              {isCurrentUser && (
                                <span className="rounded-full bg-slate-100 px-2 py-0.5 text-xs font-medium text-slate-600">
                                  You
                                </span>
                              )}
                            </div>

                            <p className="truncate text-sm text-slate-500">
                              {user.email}
                            </p>
                          </div>
                        </div>

                        <div className="flex flex-wrap items-center gap-3">
                          <span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-semibold capitalize text-slate-700">
                            {user.role.replace("_", " ")}
                          </span>

                          <span
                            className={`flex items-center gap-1 rounded-full px-3 py-1 text-xs font-semibold ${
                              user.is_active
                                ? "bg-emerald-50 text-emerald-700"
                                : "bg-slate-100 text-slate-500"
                            }`}
                          >
                            {user.is_active ? (
                              <CheckCircle2 size={13} />
                            ) : (
                              <XCircle size={13} />
                            )}

                            {user.is_active
                              ? "Active"
                              : "Inactive"}
                          </span>

                          {manageable && (
                            <>
                              <button
                                type="button"
                                onClick={() =>
                                  openEditForm(user)
                                }
                                className="flex items-center gap-1.5 rounded-lg border border-slate-200 px-3 py-2 text-xs font-medium text-slate-700 transition hover:bg-slate-50"
                              >
                                <Edit3 size={14} />
                                Edit
                              </button>

                              <button
                                type="button"
                                onClick={() =>
                                  toggleUser(user)
                                }
                                className={`flex items-center gap-1.5 rounded-lg px-3 py-2 text-xs font-medium transition ${
                                  user.is_active
                                    ? "border border-red-200 text-red-600 hover:bg-red-50"
                                    : "border border-emerald-200 text-emerald-700 hover:bg-emerald-50"
                                }`}
                              >
                                {user.is_active ? (
                                  <UserX size={14} />
                                ) : (
                                  <UserCheck size={14} />
                                )}

                                {user.is_active
                                  ? "Deactivate"
                                  : "Activate"}
                              </button>
                            </>
                          )}
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          </div>
        </section>
      </div>

      {showForm && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
          <div className="w-full max-w-lg rounded-2xl bg-white shadow-xl">
            <div className="flex items-center justify-between border-b border-slate-200 px-6 py-5">
              <div>
                <h2 className="text-lg font-semibold text-slate-900">
                  {editingUser
                    ? "Edit Team Member"
                    : "Add Team Member"}
                </h2>

                <p className="mt-1 text-sm text-slate-500">
                  {editingUser
                    ? "Update this team member's account and access."
                    : "Create a new manager or staff account."}
                </p>
              </div>

              <button
                type="button"
                onClick={closeForm}
                disabled={saving}
                className="text-slate-400 transition hover:text-slate-700 disabled:opacity-50"
              >
                <X size={20} />
              </button>
            </div>

            <form
              onSubmit={handleSubmit}
              className="space-y-5 p-6"
            >
              {formError && (
                <div className="flex items-start gap-3 rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700">
                  <XCircle size={20} className="mt-0.5 shrink-0" />
                  <div>{formError}</div>
                </div>
              )}

              <div>
                <label className="mb-2 block text-sm font-medium text-slate-700">
                  Full Name
                </label>

                <input
                  type="text"
                  value={form.full_name}
                  onChange={(event) =>
                    setForm((current) => ({
                      ...current,
                      full_name: event.target.value,
                    }))
                  }
                  className="w-full rounded-lg border border-slate-300 px-3 py-2.5 text-sm outline-none focus:border-slate-500 focus:ring-2 focus:ring-slate-200"
                  placeholder="e.g. John Mokoena"
                  disabled={saving}
                />
              </div>

              {!editingUser && (
                <>
                  <div>
                    <label className="mb-2 block text-sm font-medium text-slate-700">
                      Email
                    </label>

                    <input
                      type="email"
                      value={form.email}
                      onChange={(event) =>
                        setForm((current) => ({
                          ...current,
                          email: event.target.value,
                        }))
                      }
                      className="w-full rounded-lg border border-slate-300 px-3 py-2.5 text-sm outline-none focus:border-slate-500 focus:ring-2 focus:ring-slate-200"
                      placeholder="name@example.com"
                      disabled={saving}
                    />
                  </div>

                  <div>
                    <label className="mb-2 block text-sm font-medium text-slate-700">
                      Temporary Password
                    </label>

                    <input
                      type="password"
                      value={form.password}
                      onChange={(event) =>
                        setForm((current) => ({
                          ...current,
                          password: event.target.value,
                        }))
                      }
                      className="w-full rounded-lg border border-slate-300 px-3 py-2.5 text-sm outline-none focus:border-slate-500 focus:ring-2 focus:ring-slate-200"
                      placeholder="Enter a password"
                      disabled={saving}
                    />
                  </div>
                </>
              )}

              <div>
                <label className="mb-2 block text-sm font-medium text-slate-700">
                  Role
                </label>

                <select
                  value={form.role}
                  onChange={(event) =>
                    setForm((current) => ({
                      ...current,
                      role: event.target.value,
                    }))
                  }
                  disabled={
                    saving ||
                    (editingUser
                      ? !currentUser ||
                        currentUser.role !== "main_admin"
                      : false)
                  }
                  className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2.5 text-sm outline-none focus:border-slate-500 focus:ring-2 focus:ring-slate-200 disabled:bg-slate-100 disabled:text-slate-500"
                >
                  {canCreateRole("staff") || editingUser ? (
                    <option value="staff">Staff</option>
                  ) : null}

                  {canCreateRole("manager") || editingUser ? (
                    <option value="manager">Manager</option>
                  ) : null}
                </select>

                {!editingUser &&
                  currentUser?.role === "manager" && (
                    <p className="mt-1.5 text-xs text-slate-500">
                      Managers can create staff accounts.
                    </p>
                  )}
              </div>

              {editingUser && (
                <label className="flex items-center gap-3 rounded-lg border border-slate-200 p-3">
                  <input
                    type="checkbox"
                    checked={form.is_active}
                    onChange={(event) =>
                      setForm((current) => ({
                        ...current,
                        is_active: event.target.checked,
                      }))
                    }
                    disabled={saving}
                    className="h-4 w-4 rounded border-slate-300"
                  />

                  <span className="text-sm font-medium text-slate-700">
                    Account is active
                  </span>
                </label>
              )}

              <div className="flex justify-end gap-3 border-t border-slate-200 pt-5">
                <button
                  type="button"
                  onClick={closeForm}
                  disabled={saving}
                  className="rounded-lg border border-slate-300 px-4 py-2.5 text-sm font-medium text-slate-700 transition hover:bg-slate-50 disabled:opacity-50"
                >
                  Cancel
                </button>

                <button
                  type="submit"
                  disabled={saving}
                  className="rounded-lg bg-slate-950 px-4 py-2.5 text-sm font-medium text-white transition hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-50"
                >
                  {saving
                    ? "Saving..."
                    : editingUser
                    ? "Save Changes"
                    : "Create User"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </main>
  );
}
