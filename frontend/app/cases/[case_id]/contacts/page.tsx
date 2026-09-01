"use client";

import { FormEvent, useEffect, useState } from "react";
import {
  ArrowLeft,
  Mail,
  MapPin,
  Pencil,
  Phone,
  Plus,
  Trash2,
  UserRound,
  X,
} from "lucide-react";
import { useParams, useRouter } from "next/navigation";
import api from "@/lib/api";
import { isAuthenticated } from "@/lib/auth";

type Contact = {
  id: string;
  business_id: string;
  case_id: string;
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

type ContactForm = {
  contact_type: string;
  first_name: string;
  last_name: string;
  phone: string;
  email: string;
  relationship: string;
  organization: string;
  address: string;
  notes: string;
};

const emptyForm: ContactForm = {
  contact_type: "family",
  first_name: "",
  last_name: "",
  phone: "",
  email: "",
  relationship: "",
  organization: "",
  address: "",
  notes: "",
};

export default function ContactsPage() {
  const router = useRouter();
  const params = useParams();

  const caseId = params.case_id as string;

  const [contacts, setContacts] = useState<Contact[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const [showForm, setShowForm] = useState(false);
  const [editingContact, setEditingContact] =
    useState<Contact | null>(null);

  const [form, setForm] = useState<ContactForm>(emptyForm);
  const [saving, setSaving] = useState(false);
  const [formError, setFormError] = useState("");

  const [deletingId, setDeletingId] = useState<string | null>(
    null
  );

  useEffect(() => {
    if (!isAuthenticated()) {
      router.push("/login");
      return;
    }

    if (!caseId) {
      return;
    }

    loadContacts();
  }, [caseId, router]);

  async function loadContacts() {
    try {
      setLoading(true);
      setError("");

      const response = await api.get<Contact[]>(
        `/cases/${caseId}/contacts`
      );

      setContacts(response.data);
    } catch (err: any) {
      if (err.response?.status === 401) {
        router.push("/login");
        return;
      }

      setError(
        err.response?.data?.detail ||
          "Unable to load case contacts."
      );
    } finally {
      setLoading(false);
    }
  }

  function openAddForm() {
    setEditingContact(null);
    setForm(emptyForm);
    setFormError("");
    setShowForm(true);
  }

  function openEditForm(contact: Contact) {
    setEditingContact(contact);

    setForm({
      contact_type: contact.contact_type,
      first_name: contact.first_name,
      last_name: contact.last_name,
      phone: contact.phone || "",
      email: contact.email || "",
      relationship: contact.relationship || "",
      organization: contact.organization || "",
      address: contact.address || "",
      notes: contact.notes || "",
    });

    setFormError("");
    setShowForm(true);
  }

  function updateForm(
    field: keyof ContactForm,
    value: string
  ) {
    setForm((current) => ({
      ...current,
      [field]: value,
    }));
  }

  async function handleSubmit(
    event: FormEvent<HTMLFormElement>
  ) {
    event.preventDefault();

    setSaving(true);
    setFormError("");

    try {
      const payload = {
        contact_type: form.contact_type,
        first_name: form.first_name.trim(),
        last_name: form.last_name.trim(),
        phone: form.phone.trim() || null,
        email: form.email.trim() || null,
        relationship:
          form.relationship.trim() || null,
        organization:
          form.organization.trim() || null,
        address: form.address.trim() || null,
        notes: form.notes.trim() || null,
      };

      if (!payload.first_name || !payload.last_name) {
        setFormError(
          "First name and last name are required."
        );
        setSaving(false);
        return;
      }

      if (editingContact) {
        await api.patch(
          `/cases/contacts/${editingContact.id}`,
          payload
        );
      } else {
        await api.post(
          `/cases/${caseId}/contacts`,
          payload
        );
      }

      setShowForm(false);
      setEditingContact(null);
      setForm(emptyForm);

      await loadContacts();
    } catch (err: any) {
      if (err.response?.status === 401) {
        router.push("/login");
        return;
      }

      setFormError(
        err.response?.data?.detail ||
          "Unable to save contact."
      );
    } finally {
      setSaving(false);
    }
  }

  async function deleteContact(contact: Contact) {
    const confirmed = window.confirm(
      `Delete ${contact.first_name} ${contact.last_name}?`
    );

    if (!confirmed) {
      return;
    }

    try {
      setDeletingId(contact.id);

      await api.delete(
        `/cases/contacts/${contact.id}`
      );

      await loadContacts();
    } catch (err: any) {
      if (err.response?.status === 401) {
        router.push("/login");
        return;
      }

      setError(
        err.response?.data?.detail ||
          "Unable to delete contact."
      );
    } finally {
      setDeletingId(null);
    }
  }

  if (loading) {
    return (
      <main className="flex min-h-screen items-center justify-center bg-slate-100">
        <div className="text-sm text-slate-500">
          Loading contacts...
        </div>
      </main>
    );
  }

  return (
    <main className="min-h-screen bg-slate-100">
      <header className="border-b bg-white">
        <div className="mx-auto max-w-7xl px-6 py-5 md:px-8">
          <button
            onClick={() =>
              router.push(`/cases/${caseId}`)
            }
            className="mb-5 flex items-center gap-2 text-sm font-medium text-slate-500 hover:text-slate-900"
          >
            <ArrowLeft size={17} />
            Back to Case
          </button>

          <div className="flex flex-col justify-between gap-4 md:flex-row md:items-center">
            <div>
              <h1 className="text-2xl font-bold text-slate-900">
                Case Contacts
              </h1>

              <p className="mt-1 text-sm text-slate-500">
                Manage family members, next of kin,
                suppliers and other case contacts.
              </p>
            </div>

            <button
              type="button"
              onClick={openAddForm}
              className="flex items-center justify-center gap-2 rounded-lg bg-slate-900 px-4 py-2.5 text-sm font-semibold text-white hover:bg-slate-800"
            >
              <Plus size={17} />
              Add Contact
            </button>
          </div>
        </div>
      </header>

      <section className="mx-auto max-w-7xl p-6 md:p-8">
        {error && (
          <div className="mb-6 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
            {error}
          </div>
        )}

        {contacts.length === 0 ? (
          <div className="rounded-2xl border bg-white p-12 text-center shadow-sm">
            <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-full bg-slate-100 text-slate-500">
              <UserRound size={25} />
            </div>

            <h2 className="mt-4 text-lg font-semibold text-slate-900">
              No contacts yet
            </h2>

            <p className="mx-auto mt-2 max-w-md text-sm text-slate-500">
              Add the family members, next of kin,
              suppliers or other people connected to
              this funeral case.
            </p>

            <button
              type="button"
              onClick={openAddForm}
              className="mt-6 inline-flex items-center gap-2 rounded-lg bg-slate-900 px-4 py-2.5 text-sm font-semibold text-white hover:bg-slate-800"
            >
              <Plus size={17} />
              Add First Contact
            </button>
          </div>
        ) : (
          <div className="grid gap-5 md:grid-cols-2 xl:grid-cols-3">
            {contacts.map((contact) => (
              <ContactCard
                key={contact.id}
                contact={contact}
                deleting={
                  deletingId === contact.id
                }
                onEdit={() =>
                  openEditForm(contact)
                }
                onDelete={() =>
                  deleteContact(contact)
                }
              />
            ))}
          </div>
        )}
      </section>

      {showForm && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/50 p-4">
          <div className="max-h-[90vh] w-full max-w-3xl overflow-y-auto rounded-2xl bg-white shadow-2xl">
            <div className="sticky top-0 flex items-center justify-between border-b bg-white px-6 py-5">
              <div>
                <h2 className="text-lg font-bold text-slate-900">
                  {editingContact
                    ? "Edit Contact"
                    : "Add Contact"}
                </h2>

                <p className="mt-1 text-xs text-slate-500">
                  {editingContact
                    ? "Update contact information."
                    : "Add a person or organisation connected to this case."}
                </p>
              </div>

              <button
                type="button"
                onClick={() =>
                  setShowForm(false)
                }
                className="rounded-lg p-2 text-slate-400 hover:bg-slate-100 hover:text-slate-700"
              >
                <X size={20} />
              </button>
            </div>

            <form
              onSubmit={handleSubmit}
              className="space-y-6 p-6"
            >
              {formError && (
                <div className="rounded-lg bg-red-50 px-4 py-3 text-sm text-red-700">
                  {formError}
                </div>
              )}

              <div>
                <h3 className="mb-4 font-semibold text-slate-900">
                  Contact Information
                </h3>

                <div className="grid gap-4 md:grid-cols-2">
                  <div>
                    <label className="mb-2 block text-sm font-medium text-slate-700">
                      Contact Type
                    </label>

                    <select
                      value={form.contact_type}
                      onChange={(event) =>
                        updateForm(
                          "contact_type",
                          event.target.value
                        )
                      }
                      className="w-full rounded-lg border border-slate-300 bg-white px-4 py-3 text-sm outline-none focus:border-slate-900 focus:ring-2 focus:ring-slate-200"
                    >
                      <option value="family">
                        Family
                      </option>
                      <option value="next_of_kin">
                        Next of Kin
                      </option>
                      <option value="supplier">
                        Supplier
                      </option>
                      <option value="funeral_director">
                        Funeral Director
                      </option>
                      <option value="organization">
                        Organization
                      </option>
                      <option value="other">
                        Other
                      </option>
                    </select>
                  </div>

                  <ContactInput
                    label="Relationship"
                    value={form.relationship}
                    onChange={(value) =>
                      updateForm(
                        "relationship",
                        value
                      )
                    }
                    placeholder="e.g. Son, Daughter, Brother"
                  />

                  <ContactInput
                    label="First Name"
                    required
                    value={form.first_name}
                    onChange={(value) =>
                      updateForm(
                        "first_name",
                        value
                      )
                    }
                  />

                  <ContactInput
                    label="Last Name"
                    required
                    value={form.last_name}
                    onChange={(value) =>
                      updateForm(
                        "last_name",
                        value
                      )
                    }
                  />

                  <ContactInput
                    label="Phone"
                    type="tel"
                    value={form.phone}
                    onChange={(value) =>
                      updateForm("phone", value)
                    }
                  />

                  <ContactInput
                    label="Email"
                    type="email"
                    value={form.email}
                    onChange={(value) =>
                      updateForm("email", value)
                    }
                  />

                  <ContactInput
                    label="Organization"
                    value={form.organization}
                    onChange={(value) =>
                      updateForm(
                        "organization",
                        value
                      )
                    }
                  />
                </div>
              </div>

              <div>
                <label className="mb-2 block text-sm font-medium text-slate-700">
                  Address
                </label>

                <textarea
                  value={form.address}
                  onChange={(event) =>
                    updateForm(
                      "address",
                      event.target.value
                    )
                  }
                  rows={3}
                  className="w-full rounded-lg border border-slate-300 px-4 py-3 text-sm outline-none focus:border-slate-900 focus:ring-2 focus:ring-slate-200"
                  placeholder="Physical or postal address"
                />
              </div>

              <div>
                <label className="mb-2 block text-sm font-medium text-slate-700">
                  Notes
                </label>

                <textarea
                  value={form.notes}
                  onChange={(event) =>
                    updateForm(
                      "notes",
                      event.target.value
                    )
                  }
                  rows={4}
                  className="w-full rounded-lg border border-slate-300 px-4 py-3 text-sm outline-none focus:border-slate-900 focus:ring-2 focus:ring-slate-200"
                  placeholder="Additional contact notes..."
                />
              </div>

              <div className="flex justify-end gap-3 border-t pt-5">
                <button
                  type="button"
                  onClick={() =>
                    setShowForm(false)
                  }
                  className="rounded-lg border border-slate-300 px-5 py-2.5 text-sm font-medium text-slate-700 hover:bg-slate-50"
                >
                  Cancel
                </button>

                <button
                  type="submit"
                  disabled={saving}
                  className="rounded-lg bg-slate-900 px-5 py-2.5 text-sm font-semibold text-white hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-60"
                >
                  {saving
                    ? "Saving..."
                    : editingContact
                    ? "Save Changes"
                    : "Add Contact"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </main>
  );
}

function ContactCard({
  contact,
  deleting,
  onEdit,
  onDelete,
}: {
  contact: Contact;
  deleting: boolean;
  onEdit: () => void;
  onDelete: () => void;
}) {
  return (
    <div className="rounded-2xl border bg-white p-6 shadow-sm">
      <div className="flex items-start justify-between gap-4">
        <div className="flex items-center gap-3">
          <div className="flex h-11 w-11 items-center justify-center rounded-full bg-slate-100 text-slate-700">
            <UserRound size={20} />
          </div>

          <div>
            <h2 className="font-semibold text-slate-900">
              {contact.first_name}{" "}
              {contact.last_name}
            </h2>

            <p className="mt-0.5 text-xs font-medium uppercase tracking-wide text-slate-400">
              {formatContactType(
                contact.contact_type
              )}
            </p>
          </div>
        </div>

        <div className="flex gap-1">
          <button
            type="button"
            onClick={onEdit}
            className="rounded-lg p-2 text-slate-400 hover:bg-slate-100 hover:text-slate-700"
            title="Edit contact"
          >
            <Pencil size={16} />
          </button>

          <button
            type="button"
            onClick={onDelete}
            disabled={deleting}
            className="rounded-lg p-2 text-slate-400 hover:bg-red-50 hover:text-red-600 disabled:opacity-50"
            title="Delete contact"
          >
            <Trash2 size={16} />
          </button>
        </div>
      </div>

      <div className="mt-5 space-y-3">
        {contact.relationship && (
          <InfoRow
            label="Relationship"
            value={contact.relationship}
          />
        )}

        {contact.organization && (
          <InfoRow
            label="Organization"
            value={contact.organization}
          />
        )}

        {contact.phone && (
          <a
            href={`tel:${contact.phone}`}
            className="flex items-center gap-2 text-sm font-medium text-slate-700 hover:underline"
          >
            <Phone size={15} />
            {contact.phone}
          </a>
        )}

        {contact.email && (
          <a
            href={`mailto:${contact.email}`}
            className="flex items-center gap-2 text-sm font-medium text-slate-700 hover:underline"
          >
            <Mail size={15} />
            {contact.email}
          </a>
        )}

        {contact.address && (
          <div className="flex gap-2 text-sm text-slate-600">
            <MapPin
              size={15}
              className="mt-0.5 shrink-0"
            />

            <span className="whitespace-pre-wrap">
              {contact.address}
            </span>
          </div>
        )}
      </div>

      {contact.notes && (
        <div className="mt-5 border-t pt-4">
          <p className="text-xs font-medium uppercase tracking-wide text-slate-400">
            Notes
          </p>

          <p className="mt-1 whitespace-pre-wrap text-sm leading-6 text-slate-600">
            {contact.notes}
          </p>
        </div>
      )}
    </div>
  );
}

function ContactInput({
  label,
  value,
  onChange,
  required = false,
  type = "text",
  placeholder,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  required?: boolean;
  type?: string;
  placeholder?: string;
}) {
  return (
    <div>
      <label className="mb-2 block text-sm font-medium text-slate-700">
        {label}
        {required && (
          <span className="ml-1 text-red-500">
            *
          </span>
        )}
      </label>

      <input
        type={type}
        value={value}
        required={required}
        onChange={(event) =>
          onChange(event.target.value)
        }
        placeholder={placeholder}
        className="w-full rounded-lg border border-slate-300 px-4 py-3 text-sm outline-none focus:border-slate-900 focus:ring-2 focus:ring-slate-200"
      />
    </div>
  );
}

function InfoRow({
  label,
  value,
}: {
  label: string;
  value: string;
}) {
  return (
    <div>
      <p className="text-xs font-medium uppercase tracking-wide text-slate-400">
        {label}
      </p>

      <p className="mt-1 text-sm text-slate-700">
        {value}
      </p>
    </div>
  );
}

function formatContactType(type: string) {
  return type
    .replaceAll("_", " ")
    .replace(/\b\w/g, (letter) =>
      letter.toUpperCase()
    );
}
