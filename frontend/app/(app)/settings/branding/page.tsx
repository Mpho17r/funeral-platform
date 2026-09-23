"use client";

import {
  ChangeEvent,
  useEffect,
  useState,
} from "react";

import {
  ArrowLeft,
  Check,
  Image as ImageIcon,
  Loader2,
  Palette,
  Save,
  ShieldCheck,
  Upload,
} from "lucide-react";

import { useRouter } from "next/navigation";

import { useBranding } from "@/components/BrandingProvider";
import api from "@/lib/api";

type Business = {
  id: string;
  name: string;
  slug: string;
  logo_url: string | null;
  primary_color: string;
  secondary_color: string;
  watermark_url: string | null;
  watermark_opacity: number;
  theme_preference: "light" | "dark" | "system";
};

function getErrorMessage(
  error: any,
  fallback: string,
) {
  const detail = error?.response?.data?.detail;

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
          const location = Array.isArray(item.loc)
            ? item.loc.join(".")
            : "";

          return location
            ? `${location}: ${item.msg}`
            : item.msg;
        }

        return null;
      })
      .filter(Boolean)
      .join(" | ");
  }

  if (
    detail &&
    typeof detail === "object" &&
    typeof detail.msg === "string"
  ) {
    return detail.msg;
  }

  if (typeof error?.message === "string") {
    return error.message;
  }

  return fallback;
}

export default function BrandingPage() {
  const router = useRouter();

  const {
    refreshBranding,
  } = useBranding();

  const [business, setBusiness] =
    useState<Business | null>(null);

  const [logoPreview, setLogoPreview] =
    useState<string | null>(null);

  const [watermarkPreview, setWatermarkPreview] =
    useState<string | null>(null);

  const [primaryColor, setPrimaryColor] =
    useState("#000000");

  const [secondaryColor, setSecondaryColor] =
    useState("#64748b");

  const [watermarkOpacity, setWatermarkOpacity] =
    useState(0.05);

  const [themePreference, setThemePreference] =
    useState<"light" | "dark" | "system">(
      "system",
    );

  const [loading, setLoading] =
    useState(true);

  const [saving, setSaving] =
    useState(false);

  const [uploadingLogo, setUploadingLogo] =
    useState(false);

  const [
    uploadingWatermark,
    setUploadingWatermark,
  ] = useState(false);

  const [message, setMessage] =
    useState("");

  const [error, setError] =
    useState("");

  function revokeUrl(url: string | null) {
    if (url) {
      URL.revokeObjectURL(url);
    }
  }

  async function loadProtectedImage(
    url: string | null,
  ): Promise<string | null> {
    if (!url) {
      return null;
    }

    try {
      const response = await api.get(
        url,
        {
          responseType: "blob",
        },
      );

      return URL.createObjectURL(
        response.data,
      );
    } catch {
      return null;
    }
  }

  async function loadBusiness() {
    try {
      setLoading(true);
      setError("");
      setMessage("");

      const meResponse =
        await api.get("/auth/me");

      const businessId =
        meResponse.data?.business_id;

      if (!businessId) {
        throw new Error(
          "Your account is not linked to a business.",
        );
      }

      const businessResponse =
        await api.get(
          `/businesses/${businessId}`,
        );

      const data: Business =
        businessResponse.data;

      setBusiness(data);

      setPrimaryColor(
        data.primary_color,
      );

      setSecondaryColor(
        data.secondary_color,
      );

      setWatermarkOpacity(
        data.watermark_opacity,
      );

      setThemePreference(
        data.theme_preference,
      );

      const [
        newLogoPreview,
        newWatermarkPreview,
      ] = await Promise.all([
        loadProtectedImage(
          data.logo_url,
        ),
        loadProtectedImage(
          data.watermark_url,
        ),
      ]);

      setLogoPreview(
        (previous) => {
          revokeUrl(previous);
          return newLogoPreview;
        },
      );

      setWatermarkPreview(
        (previous) => {
          revokeUrl(previous);
          return newWatermarkPreview;
        },
      );
    } catch (err: any) {
      setError(
        getErrorMessage(
          err,
          "Unable to load business branding.",
        ),
      );
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadBusiness();

    return () => {
      revokeUrl(logoPreview);
      revokeUrl(watermarkPreview);
    };

    // Load once when the page mounts.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function uploadFile(
    file: File,
    type: "logo" | "watermark",
  ) {
    if (!business) {
      return;
    }

    setError("");
    setMessage("");

    if (
      ![
        "image/jpeg",
        "image/png",
        "image/webp",
      ].includes(file.type)
    ) {
      setError(
        "Please select a JPG, PNG, or WebP image.",
      );
      return;
    }

    if (file.size > 5 * 1024 * 1024) {
      setError(
        "The image must be 5 MB or smaller.",
      );
      return;
    }

    const formData = new FormData();

    formData.append(
      "file",
      file,
    );

    try {
      if (type === "logo") {
        setUploadingLogo(true);
      } else {
        setUploadingWatermark(true);
      }

      const response =
        await api.post<Business>(
          `/businesses/${business.id}/branding/${type}`,
          formData,
        );

      const updatedBusiness =
        response.data;

      setBusiness(
        updatedBusiness,
      );

      setPrimaryColor(
        updatedBusiness.primary_color,
      );

      setSecondaryColor(
        updatedBusiness.secondary_color,
      );

      setWatermarkOpacity(
        updatedBusiness.watermark_opacity,
      );

      setThemePreference(
        updatedBusiness.theme_preference,
      );

      if (type === "logo") {
        const newPreview =
          await loadProtectedImage(
            updatedBusiness.logo_url,
          );

        setLogoPreview(
          (previous) => {
            revokeUrl(previous);
            return newPreview;
          },
        );

        setMessage(
          "Business logo uploaded successfully.",
        );
      } else {
        const newPreview =
          await loadProtectedImage(
            updatedBusiness.watermark_url,
          );

        setWatermarkPreview(
          (previous) => {
            revokeUrl(previous);
            return newPreview;
          },
        );

        setMessage(
          "Background watermark uploaded successfully.",
        );
      }

      await refreshBranding();
    } catch (err: any) {
      setError(
        getErrorMessage(
          err,
          `Unable to upload ${type}.`,
        ),
      );
    } finally {
      setUploadingLogo(false);
      setUploadingWatermark(false);
    }
  }

  function handleLogoChange(
    event: ChangeEvent<HTMLInputElement>,
  ) {
    const file =
      event.target.files?.[0];

    if (file) {
      void uploadFile(
        file,
        "logo",
      );
    }

    event.target.value = "";
  }

  function handleWatermarkChange(
    event: ChangeEvent<HTMLInputElement>,
  ) {
    const file =
      event.target.files?.[0];

    if (file) {
      void uploadFile(
        file,
        "watermark",
      );
    }

    event.target.value = "";
  }

  async function saveBranding() {
    if (!business) {
      return;
    }

    try {
      setSaving(true);
      setError("");
      setMessage("");

      const response =
        await api.patch<Business>(
          `/businesses/${business.id}/branding`,
          {
            primary_color:
              primaryColor,
            secondary_color:
              secondaryColor,
            watermark_opacity:
              watermarkOpacity,
            theme_preference:
              themePreference,
          },
        );

      const updatedBusiness =
        response.data;

      setBusiness(
        updatedBusiness,
      );

      setPrimaryColor(
        updatedBusiness.primary_color,
      );

      setSecondaryColor(
        updatedBusiness.secondary_color,
      );

      setWatermarkOpacity(
        updatedBusiness.watermark_opacity,
      );

      setThemePreference(
        updatedBusiness.theme_preference,
      );

      await refreshBranding();

      setMessage(
        "Branding settings saved successfully.",
      );
    } catch (err: any) {
      setError(
        getErrorMessage(
          err,
          "Unable to save branding settings.",
        ),
      );
    } finally {
      setSaving(false);
    }
  }

  function resetBranding() {
    if (!business) {
      return;
    }

    setPrimaryColor(
      business.primary_color,
    );

    setSecondaryColor(
      business.secondary_color,
    );

    setWatermarkOpacity(
      business.watermark_opacity,
    );

    setThemePreference(
      business.theme_preference,
    );

    setMessage(
      "Unsaved branding changes have been reset.",
    );

    setError("");
  }

  if (loading) {
    return (
      <main className="flex min-h-screen items-center justify-center bg-slate-100 text-slate-900 dark:bg-slate-950 dark:text-slate-100">
        <Loader2
          size={28}
          className="animate-spin"
        />
      </main>
    );
  }

  if (!business) {
    return (
      <main className="flex min-h-screen items-center justify-center bg-slate-100 p-8 text-slate-900 dark:bg-slate-950 dark:text-slate-100">
        <div className="max-w-md text-center">
          <p className="mb-4 text-red-500">
            {error ||
              "Business could not be loaded."}
          </p>

          <button
            type="button"
            onClick={() =>
              router.push("/settings")
            }
            className="rounded-lg px-5 py-3 text-sm font-semibold text-white"
            style={{
              backgroundColor:
                "var(--brand-primary, #0f172a)",
            }}
          >
            Back to Settings
          </button>
        </div>
      </main>
    );
  }

  return (
    <main className="min-h-screen overflow-y-auto bg-transparent">
      <div className="mx-auto max-w-6xl p-6 lg:p-8">

        {/* HEADER */}
        <div className="mb-8 flex items-start justify-between gap-4">
          <div>
            <button
              type="button"
              onClick={() =>
                router.push("/settings")
              }
              className="mb-4 flex items-center gap-2 text-sm font-medium text-[var(--fos-text-secondary)] transition hover:text-[var(--fos-text)]"
            >
              <ArrowLeft size={16} />
              Back to Settings
            </button>

            <h1 className="text-3xl font-bold text-[var(--fos-text)]">
              Business Branding
            </h1>

            <p className="mt-2 max-w-2xl text-sm leading-6 text-[var(--fos-text-secondary)]">
              Customize how{" "}
              <span className="font-medium text-[var(--fos-text)]">
                {business.name}
              </span>{" "}
              appears throughout FuneralOS.
            </p>
          </div>

          <div className="hidden items-center gap-2 rounded-full border border-[var(--fos-border)] bg-[var(--fos-surface)] px-4 py-2 text-sm font-medium text-[var(--fos-text)] md:flex">
            <ShieldCheck size={16} />
            Main Admin
          </div>
        </div>

        {/* MESSAGES */}
        {message && (
          <div className="mb-6 flex items-center gap-2 rounded-lg border border-green-200 bg-green-50 px-4 py-3 text-sm font-medium text-green-700 dark:border-green-900 dark:bg-green-950 dark:text-green-300">
            <Check size={17} />
            {message}
          </div>
        )}

        {error && (
          <div className="mb-6 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm font-medium text-red-700 dark:border-red-900 dark:bg-red-950 dark:text-red-300">
            {error}
          </div>
        )}

        {/* BRAND ASSETS */}
        <div className="mb-6">
          <div className="mb-4">
            <h2 className="text-xl font-bold text-[var(--fos-text)]">
              Brand Assets
            </h2>

            <p className="mt-1 text-sm text-[var(--fos-text-secondary)]">
              Upload the visual assets that identify your funeral business.
            </p>
          </div>

          <div className="grid gap-6 lg:grid-cols-2">

            {/* BUSINESS LOGO */}
            <section className="rounded-2xl border border-[var(--fos-border)] bg-[var(--fos-surface)] p-6 shadow-sm">
              <div className="mb-5 flex items-start gap-3">
                <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-[var(--fos-surface-muted)] text-[var(--fos-text)]">
                  <ImageIcon size={21} />
                </div>

                <div>
                  <h3 className="text-lg font-semibold text-[var(--fos-text)]">
                    Business Logo
                  </h3>

                  <p className="mt-1 text-sm leading-5 text-[var(--fos-text-secondary)]">
                    Your business logo will appear throughout the FuneralOS interface.
                  </p>
                </div>
              </div>

              <div className="mb-5 flex min-h-44 items-center justify-center rounded-xl border border-dashed border-[var(--fos-border)] bg-[var(--fos-surface-muted)] p-6">
                {logoPreview ? (
                  <img
                    src={logoPreview}
                    alt={`${business.name} logo`}
                    className="max-h-32 max-w-full object-contain"
                  />
                ) : (
                  <div className="text-center text-[var(--fos-text-muted)]">
                    <ImageIcon
                      size={42}
                      className="mx-auto mb-3 opacity-50"
                    />

                    <p className="text-sm font-medium">
                      No business logo uploaded
                    </p>

                    <p className="mt-1 text-xs">
                      Upload your official business logo.
                    </p>
                  </div>
                )}
              </div>

              <label className="flex cursor-pointer items-center justify-center gap-2 rounded-lg border border-[var(--fos-border)] bg-[var(--fos-surface)] px-4 py-3 text-sm font-semibold text-[var(--fos-text)] transition hover:bg-[var(--fos-surface-muted)]">
                {uploadingLogo ? (
                  <>
                    <Loader2
                      size={17}
                      className="animate-spin"
                    />
                    Uploading Logo...
                  </>
                ) : (
                  <>
                    <Upload size={17} />
                    Upload Business Logo
                  </>
                )}

                <input
                  type="file"
                  accept="image/png,image/jpeg,image/webp"
                  className="hidden"
                  onChange={handleLogoChange}
                  disabled={uploadingLogo}
                />
              </label>

              <p className="mt-2 text-xs text-[var(--fos-text-muted)]">
                PNG, JPG or WebP · Maximum 5 MB
              </p>
            </section>

            {/* BACKGROUND WATERMARK */}
            <section className="rounded-2xl border border-[var(--fos-border)] bg-[var(--fos-surface)] p-6 shadow-sm">
              <div className="mb-5 flex items-start gap-3">
                <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-[var(--fos-surface-muted)] text-[var(--fos-text)]">
                  <ImageIcon size={21} />
                </div>

                <div>
                  <h3 className="text-lg font-semibold text-[var(--fos-text)]">
                    Background Watermark
                  </h3>

                  <p className="mt-1 text-sm leading-5 text-[var(--fos-text-secondary)]">
                    A subtle business identity displayed behind your FuneralOS content.
                  </p>
                </div>
              </div>

              <div className="relative mb-5 flex min-h-44 items-center justify-center overflow-hidden rounded-xl border border-dashed border-[var(--fos-border)] bg-[var(--fos-surface-muted)] p-6">
                {watermarkPreview ? (
                  <img
                    src={watermarkPreview}
                    alt={`${business.name} watermark`}
                    className="max-h-32 max-w-full object-contain"
                    style={{
                      opacity:
                        watermarkOpacity,
                    }}
                  />
                ) : (
                  <div className="text-center text-[var(--fos-text-muted)]">
                    <ImageIcon
                      size={42}
                      className="mx-auto mb-3 opacity-50"
                    />

                    <p className="text-sm font-medium">
                      No background watermark uploaded
                    </p>

                    <p className="mt-1 text-xs">
                      Upload an image to use as your watermark.
                    </p>
                  </div>
                )}
              </div>

              <label className="flex cursor-pointer items-center justify-center gap-2 rounded-lg border border-[var(--fos-border)] bg-[var(--fos-surface)] px-4 py-3 text-sm font-semibold text-[var(--fos-text)] transition hover:bg-[var(--fos-surface-muted)]">
                {uploadingWatermark ? (
                  <>
                    <Loader2
                      size={17}
                      className="animate-spin"
                    />
                    Uploading Watermark...
                  </>
                ) : (
                  <>
                    <Upload size={17} />
                    Upload Background Watermark
                  </>
                )}

                <input
                  type="file"
                  accept="image/png,image/jpeg,image/webp"
                  className="hidden"
                  onChange={handleWatermarkChange}
                  disabled={uploadingWatermark}
                />
              </label>

              <p className="mt-2 text-xs text-[var(--fos-text-muted)]">
                PNG, JPG or WebP · Maximum 5 MB
              </p>
            </section>
          </div>
        </div>

        {/* BRAND CONFIGURATION */}
        <div className="mb-6">
          <div className="mb-4">
            <h2 className="text-xl font-bold text-[var(--fos-text)]">
              Brand Configuration
            </h2>

            <p className="mt-1 text-sm text-[var(--fos-text-secondary)]">
              Configure your business colours and application appearance.
            </p>
          </div>

          <div className="grid gap-6 lg:grid-cols-2">

            {/* COLOURS */}
            <section className="rounded-2xl border border-[var(--fos-border)] bg-[var(--fos-surface)] p-6 shadow-sm">
              <div className="mb-6 flex items-start gap-3">
                <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-[var(--fos-surface-muted)] text-[var(--fos-text)]">
                  <Palette size={21} />
                </div>

                <div>
                  <h3 className="text-lg font-semibold text-[var(--fos-text)]">
                    Brand Colours
                  </h3>

                  <p className="mt-1 text-sm text-[var(--fos-text-secondary)]">
                    Set the primary and secondary colours for your business.
                  </p>
                </div>
              </div>

              <div className="space-y-5">

                <div>
                  <label className="mb-2 block text-sm font-medium text-[var(--fos-text)]">
                    Primary Colour
                  </label>

                  <div className="flex gap-3">
                    <input
                      type="color"
                      value={primaryColor}
                      onChange={(e) =>
                        setPrimaryColor(
                          e.target.value,
                        )
                      }
                      className="h-11 w-16 cursor-pointer rounded-lg border border-[var(--fos-border)] bg-transparent p-1"
                    />

                    <input
                      type="text"
                      value={primaryColor}
                      onChange={(e) =>
                        setPrimaryColor(
                          e.target.value,
                        )
                      }
                      className="flex-1 rounded-lg border border-[var(--fos-border)] bg-[var(--fos-surface)] px-3 text-sm uppercase text-[var(--fos-text)] outline-none focus:ring-2 focus:ring-[var(--brand-primary)]"
                    />
                  </div>
                </div>

                <div>
                  <label className="mb-2 block text-sm font-medium text-[var(--fos-text)]">
                    Secondary Colour
                  </label>

                  <div className="flex gap-3">
                    <input
                      type="color"
                      value={secondaryColor}
                      onChange={(e) =>
                        setSecondaryColor(
                          e.target.value,
                        )
                      }
                      className="h-11 w-16 cursor-pointer rounded-lg border border-[var(--fos-border)] bg-transparent p-1"
                    />

                    <input
                      type="text"
                      value={secondaryColor}
                      onChange={(e) =>
                        setSecondaryColor(
                          e.target.value,
                        )
                      }
                      className="flex-1 rounded-lg border border-[var(--fos-border)] bg-[var(--fos-surface)] px-3 text-sm uppercase text-[var(--fos-text)] outline-none focus:ring-2 focus:ring-[var(--brand-primary)]"
                    />
                  </div>
                </div>

              </div>
            </section>

            {/* APPEARANCE */}
            <section className="rounded-2xl border border-[var(--fos-border)] bg-[var(--fos-surface)] p-6 shadow-sm">
              <div className="mb-6">
                <h3 className="text-lg font-semibold text-[var(--fos-text)]">
                  Application Appearance
                </h3>

                <p className="mt-1 text-sm text-[var(--fos-text-secondary)]">
                  Choose the default appearance for this business.
                </p>
              </div>

              <label className="mb-2 block text-sm font-medium text-[var(--fos-text)]">
                Theme
              </label>

              <select
                value={themePreference}
                onChange={(e) =>
                  setThemePreference(
                    e.target.value as
                      | "light"
                      | "dark"
                      | "system",
                  )
                }
                className="w-full rounded-lg border border-[var(--fos-border)] bg-[var(--fos-surface)] px-3 py-3 text-sm text-[var(--fos-text)] outline-none focus:ring-2 focus:ring-[var(--brand-primary)]"
              >
                <option value="system">
                  System preference
                </option>

                <option value="light">
                  Light
                </option>

                <option value="dark">
                  Dark
                </option>
              </select>

              <div className="mt-6">
                <label className="mb-2 flex justify-between text-sm font-medium text-[var(--fos-text)]">
                  <span>
                    Watermark Opacity
                  </span>

                  <span>
                    {Math.round(
                      watermarkOpacity * 100,
                    )}
                    %
                  </span>
                </label>

                <input
                  type="range"
                  min="0"
                  max="1"
                  step="0.01"
                  value={watermarkOpacity}
                  onChange={(e) =>
                    setWatermarkOpacity(
                      Number(
                        e.target.value,
                      ),
                    )
                  }
                  className="w-full"
                />

                <p className="mt-2 text-xs text-[var(--fos-text-muted)]">
                  Adjust how visible the background watermark appears.
                </p>
              </div>
            </section>
          </div>
        </div>

        {/* BRAND PREVIEW */}
        <section className="rounded-2xl border border-[var(--fos-border)] bg-[var(--fos-surface)] p-6 shadow-sm">
          <div className="mb-5">
            <h2 className="text-lg font-semibold text-[var(--fos-text)]">
              Brand Preview
            </h2>

            <p className="mt-1 text-sm text-[var(--fos-text-secondary)]">
              Preview how your business branding will appear inside FuneralOS.
            </p>
          </div>

          <div
            className="relative overflow-hidden rounded-xl p-6 text-white"
            style={{
              backgroundColor:
                primaryColor,
            }}
          >
            {watermarkPreview && (
              <img
                src={watermarkPreview}
                alt=""
                className="pointer-events-none absolute inset-0 m-auto max-h-full max-w-full object-contain"
                style={{
                  opacity:
                    watermarkOpacity,
                }}
              />
            )}

            <div className="relative z-10">
              {logoPreview && (
                <img
                  src={logoPreview}
                  alt=""
                  className="mb-4 h-12 max-w-48 object-contain object-left"
                />
              )}

              <h3 className="text-xl font-bold">
                {business.name}
              </h3>

              <p className="mt-1 text-sm opacity-80">
                Funeral Management Platform
              </p>

              <div
                className="mt-5 inline-flex rounded-lg px-4 py-2 text-sm font-semibold"
                style={{
                  backgroundColor:
                    secondaryColor,
                }}
              >
                Example Action
              </div>
            </div>
          </div>
        </section>

        {/* ACTIONS */}
        <div className="mt-6 flex flex-col-reverse gap-3 sm:flex-row sm:justify-end">
          <button
            type="button"
            onClick={resetBranding}
            className="rounded-lg border border-[var(--fos-border)] bg-[var(--fos-surface)] px-5 py-3 text-sm font-semibold text-[var(--fos-text)] transition hover:bg-[var(--fos-surface-muted)]"
          >
            Reset Changes
          </button>

          <button
            type="button"
            onClick={saveBranding}
            disabled={saving}
            className="flex items-center justify-center gap-2 rounded-lg px-5 py-3 text-sm font-semibold text-white transition hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-60"
            style={{
              backgroundColor:
                primaryColor,
            }}
          >
            {saving ? (
              <Loader2
                size={17}
                className="animate-spin"
              />
            ) : (
              <Save size={17} />
            )}

            {saving
              ? "Saving..."
              : "Save Branding"}
          </button>
        </div>

      </div>
    </main>
  );
}

