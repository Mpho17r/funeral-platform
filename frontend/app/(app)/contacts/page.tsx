"use client";

import { useEffect, useMemo, useState } from "react";

import {
  ContactRound,
  Loader2,
  Mail,
  Phone,
  RefreshCw,
  Search,
} from "lucide-react";

import { useRouter } from "next/navigation";

import api from "@/lib/api";

import { isAuthenticated } from "@/lib/auth";

type WorkspaceContact = {
  id: string;
  business_id: string;
  case_id: string;
  case_number: string;
  deceased_full_name: string;
  contact_type: string;
  first_name: string;
  last_name: string;
  phone: string | null;
  email: string | null;
  relationship: string | null;
  organization: string | null;
  address: string | null;
  notes: string | null;
  created_at: string;
  updated_at: string;
};

function getApiErrorMessage(err: any, fallback: string) {
  const detail = err?.response?.data?.detail;

  if (typeof detail === "string") {
    return detail;
  }

  if (Array.isArray(detail)) {
    return detail
      .map((item: any) => {
        if (typeof item === "string") {
          return item;
        }

        if (item?.msg) {
          return item.msg;
        }

        return "Invalid request.";
      })
      .join(" ");
  }

  if (typeof err?.message === "string") {
    return err.message;
  }

  return fallback;
}

function formatContactType(value: string) {
  return value
    .replaceAll("_", " ")
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function getContactTypeClass(value: string) {
  switch (value.toLowerCase()) {
    case "family":
      return "bg-blue-50 text-blue-700";
    case "next_of_kin":
      return "bg-emerald-50 text-emerald-700";
    case "supplier":
      return "bg-amber-50 text-amber-700";
    default:
      return "bg-slate-100 text-slate-700";
  }
}

export default function ContactsWorkspacePage() {
  const router = useRouter();

  const [contacts, setContacts] = useState<WorkspaceContact[]>([]);
  const [loading, setLoading] = useState(true);
  const [pageError, setPageError] = useState("");
  const [search, setSearch] = useState("");
  const [typeFilter, setTypeFilter] = useState("all");

  useEffect(() => {
    if (!isAuthenticated()) {
      router.push("/login");
      return;
    }

    loadContacts();
  }, [router]);

  async function loadContacts() {
    try {
      setLoading(true);
      setPageError("");

      const response = await api.get<WorkspaceContact[]>(
        "/contacts"
      );

      setContacts(response.data);
    } catch (err: any) {
      if (err.response?.status === 401) {
        router.push("/login");
        return;
      }

      setPageError(
        getApiErrorMessage(
          err,
          "Unable to load the contact workspace."
        )
      );
    } finally {
      setLoading(false);
    }
  }

  const contactTypes = useMemo(() => {
    return Array.from(
      new Set(contacts.map((contact) => contact.contact_type))
    ).sort();
  }, [contacts]);

  const filteredContacts = useMemo(() => {
    const query = search.trim().toLowerCase();

    return contacts.filter((contact) => {
      const matchesType =
        typeFilter === "all" ||
        contact.contact_type === typeFilter;

      if (!matchesType) {
        return false;
      }

      if (!query) {
        return true;
      }

      const searchableText = [
        contact.first_name,
        contact.last_name,
        contact.phone,
        contact.email,
        contact.relationship,
        contact.organization,
        contact.case_number,
        contact.deceased_full_name,
      ]
        .filter(Boolean)
        .join(" ")
        .toLowerCase();

      return searchableText.includes(query);
    });
  }, [contacts, search, typeFilter]);

  return (
    <main className="space-y-6">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <div className="flex items-center gap-3">
            <div className="rounded-xl bg-slate-100 p-3">
              <ContactRound className="h-6 w-6 text-slate-700" />
            </div>

            <div>
              <h1 className="text-2xl font-semibold text-slate-900">
                Contacts
              </h1>

              <p className="text-sm text-slate-500">
                Business-wide contact workspace
              </p>
            </div>
          </div>
        </div>

        <button
          type="button"
          onClick={loadContacts}
          disabled={loading}
          className="inline-flex items-center justify-center gap-2 rounded-lg border border-slate-200 bg-white px-4 py-2 text-sm font-medium text-slate-700 shadow-sm transition hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-60"
        >
          <RefreshCw className="h-4 w-4" />
          Refresh
        </button>
      </div>

      <section className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-end">
          <div className="w-full lg:flex-1">
            <label
              htmlFor="contact-search"
              className="mb-1 block text-sm font-medium text-slate-700"
            >
              Search
            </label>

            <div className="relative">
              <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />

              <input
                id="contact-search"
                type="search"
                value={search}
                onChange={(event) =>
                  setSearch(event.target.value)
                }
                placeholder="Name, phone, email, case or deceased..."
                className="w-full rounded-lg border border-slate-300 bg-white py-2 pl-9 pr-3 text-sm outline-none focus:border-slate-500"
              />
            </div>
          </div>

          <div className="w-full lg:w-56">
            <label
              htmlFor="contact-type-filter"
              className="mb-1 block text-sm font-medium text-slate-700"
            >
              Contact type
            </label>

            <select
              id="contact-type-filter"
              value={typeFilter}
              onChange={(event) =>
                setTypeFilter(event.target.value)
              }
              className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm outline-none focus:border-slate-500"
            >
              <option value="all">All types</option>

              {contactTypes.map((type) => (
                <option key={type} value={type}>
                  {formatContactType(type)}
                </option>
              ))}
            </select>
          </div>

          <div className="text-sm text-slate-500">
            Showing{" "}
            <span className="font-semibold text-slate-800">
              {filteredContacts.length}
            </span>{" "}
            of{" "}
            <span className="font-semibold text-slate-800">
              {contacts.length}
            </span>{" "}
            contacts
          </div>
        </div>
      </section>

      {pageError && (
        <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          {pageError}
        </div>
      )}

      <section className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
        {loading ? (
          <div className="flex items-center justify-center gap-2 px-6 py-16 text-sm text-slate-500">
            <Loader2 className="h-5 w-5 animate-spin" />
            Loading contacts...
          </div>
        ) : filteredContacts.length === 0 ? (
          <div className="px-6 py-16 text-center">
            <ContactRound className="mx-auto mb-3 h-10 w-10 text-slate-300" />

            <h2 className="text-lg font-semibold text-slate-800">
              No contacts found
            </h2>

            <p className="mt-1 text-sm text-slate-500">
              There are no contacts matching the current
              search or filters.
            </p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-slate-200">
              <thead className="bg-slate-50">
                <tr>
                  <th className="px-6 py-3 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">
                    Contact
                  </th>

                  <th className="px-6 py-3 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">
                    Type
                  </th>

                  <th className="px-6 py-3 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">
                    Phone / Email
                  </th>

                  <th className="px-6 py-3 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">
                    Case
                  </th>

                  <th className="px-6 py-3 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">
                    Deceased
                  </th>
                </tr>
              </thead>

              <tbody className="divide-y divide-slate-100">
                {filteredContacts.map((contact) => (
                  <tr
                    key={contact.id}
                    className="transition hover:bg-slate-50"
                  >
                    <td className="px-6 py-4">
                      <div className="font-medium text-slate-900">
                        {contact.first_name}{" "}
                        {contact.last_name}
                      </div>

                      {contact.relationship && (
                        <div className="mt-1 text-sm text-slate-500">
                          {contact.relationship}
                        </div>
                      )}

                      {contact.organization && (
                        <div className="mt-1 text-xs text-slate-400">
                          {contact.organization}
                        </div>
                      )}
                    </td>

                    <td className="px-6 py-4">
                      <span
                        className={`inline-flex rounded-full px-2.5 py-1 text-xs font-medium ${getContactTypeClass(
                          contact.contact_type
                        )}`}
                      >
                        {formatContactType(
                          contact.contact_type
                        )}
                      </span>
                    </td>

                    <td className="px-6 py-4">
                      <div className="space-y-1 text-sm">
                        {contact.phone ? (
                          <a
                            href={`tel:${contact.phone}`}
                            className="flex items-center gap-2 text-slate-700 hover:text-slate-900 hover:underline"
                          >
                            <Phone className="h-3.5 w-3.5" />
                            {contact.phone}
                          </a>
                        ) : (
                          <div className="text-slate-400">
                            No phone
                          </div>
                        )}

                        {contact.email ? (
                          <a
                            href={`mailto:${contact.email}`}
                            className="flex items-center gap-2 text-slate-700 hover:text-slate-900 hover:underline"
                          >
                            <Mail className="h-3.5 w-3.5" />
                            {contact.email}
                          </a>
                        ) : (
                          <div className="text-slate-400">
                            No email
                          </div>
                        )}
                      </div>
                    </td>

                    <td className="px-6 py-4">
                      <button
                        type="button"
                        onClick={() =>
                          router.push(
                            `/cases/${contact.case_id}`
                          )
                        }
                        className="text-left"
                      >
                        <div className="font-medium text-slate-900 hover:underline">
                          {contact.case_number}
                        </div>
                      </button>
                    </td>

                    <td className="px-6 py-4 text-sm text-slate-700">
                      {contact.deceased_full_name}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </main>
  );
}
