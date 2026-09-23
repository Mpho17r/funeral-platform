"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from "react";

import api from "@/lib/api";

type BrandingData = {
  name?: string;
  logo_url?: string | null;
  watermark_url?: string | null;
  primary_color?: string | null;
  secondary_color?: string | null;
  watermark_opacity?: number | null;
  theme_preference?: string | null;
};

type BrandingContextType = {
  branding: BrandingData | null;
  loading: boolean;
  logoObjectUrl: string | null;
  watermarkObjectUrl: string | null;
  refreshBranding: () => Promise<void>;
};

const BrandingContext =
  createContext<BrandingContextType>({
    branding: null,
    loading: true,
    logoObjectUrl: null,
    watermarkObjectUrl: null,
    refreshBranding: async () => {},
  });

export function BrandingProvider({
  children,
}: {
  children: ReactNode;
}) {
  const [branding, setBranding] =
    useState<BrandingData | null>(null);

  const [loading, setLoading] =
    useState(true);

  const [logoObjectUrl, setLogoObjectUrl] =
    useState<string | null>(null);

  const [watermarkObjectUrl, setWatermarkObjectUrl] =
    useState<string | null>(null);

  const refreshBranding = useCallback(async () => {
    const token =
      typeof window !== "undefined"
        ? localStorage.getItem("access_token")
        : null;

    /*
     * No authenticated user means there is no
     * business whose branding we can load.
     */
    if (!token) {
      setBranding(null);
      setLogoObjectUrl(null);
      setWatermarkObjectUrl(null);
      setLoading(false);
      return;
    }

    try {
      setLoading(true);

      /*
       * First get the authenticated user.
       *
       * /auth/me returns the current user,
       * including business_id.
       */
      const meResponse =
        await api.get("/auth/me");

      const currentUser =
        meResponse.data;

      console.log(
        "[Branding] CURRENT USER:",
        JSON.stringify(
          currentUser,
          null,
          2,
        ),
      );

      const businessId =
        currentUser?.business_id;

      if (!businessId) {
        console.error(
          "[Branding] No business_id found for authenticated user.",
        );

        setBranding(null);
        setLogoObjectUrl(null);
        setWatermarkObjectUrl(null);

        return;
      }

      /*
       * Load the actual business.
       */
      const businessResponse =
        await api.get(
          `/businesses/${businessId}`,
        );

      const data =
        businessResponse.data;

      console.log(
        "[Branding] FULL BUSINESS RESPONSE:",
        JSON.stringify(
          data,
          null,
          2,
        ),
      );

      console.log(
        "[Branding] LOGO URL:",
        data.logo_url,
      );

      console.log(
        "[Branding] WATERMARK URL:",
        data.watermark_url,
      );

      const brandingData: BrandingData = {
        name: data.name,
        logo_url: data.logo_url,
        watermark_url:
          data.watermark_url,
        primary_color:
          data.primary_color,
        secondary_color:
          data.secondary_color,
        watermark_opacity:
          data.watermark_opacity,
        theme_preference:
          data.theme_preference,
      };

      setBranding(brandingData);

      /*
       * Apply business colours globally.
       */
      if (data.primary_color) {
        document.documentElement.style.setProperty(
          "--primary-color",
          data.primary_color,
        );
      }

      if (data.secondary_color) {
        document.documentElement.style.setProperty(
          "--secondary-color",
          data.secondary_color,
        );
      }

      /*
       * IMPORTANT:
       *
       * The logo and watermark endpoints are protected
       * by the backend authentication dependency.
       *
       * Therefore we cannot simply put the relative URL
       * into <img src="..."> because the browser would:
       *
       * 1. Request localhost:3000 instead of port 8000.
       * 2. Not automatically include our Axios Bearer token.
       *
       * Instead, download the files through the authenticated
       * Axios instance and create local object URLs.
       */

      /*
       * LOGO
       */
      if (data.logo_url) {
        try {
          const logoResponse =
            await api.get(
              data.logo_url,
              {
                responseType: "blob",
              },
            );

          const logoUrl =
            URL.createObjectURL(
              logoResponse.data,
            );

          setLogoObjectUrl(
            (previousUrl) => {
              if (previousUrl) {
                URL.revokeObjectURL(
                  previousUrl,
                );
              }

              return logoUrl;
            },
          );

          console.log(
            "[Branding] LOGO LOADED SUCCESSFULLY",
          );
        } catch (error) {
          console.error(
            "[Branding] Failed to load logo:",
            error,
          );

          setLogoObjectUrl(null);
        }
      } else {
        setLogoObjectUrl(null);
      }

      /*
       * WATERMARK
       */
      if (data.watermark_url) {
        try {
          const watermarkResponse =
            await api.get(
              data.watermark_url,
              {
                responseType: "blob",
              },
            );

          const watermarkUrl =
            URL.createObjectURL(
              watermarkResponse.data,
            );

          setWatermarkObjectUrl(
            (previousUrl) => {
              if (previousUrl) {
                URL.revokeObjectURL(
                  previousUrl,
                );
              }

              return watermarkUrl;
            },
          );

          console.log(
            "[Branding] WATERMARK LOADED SUCCESSFULLY",
          );
        } catch (error) {
          console.error(
            "[Branding] Failed to load watermark:",
            error,
          );

          setWatermarkObjectUrl(null);
        }
      } else {
        setWatermarkObjectUrl(null);
      }
    } catch (error) {
      console.error(
        "[Branding] Failed to load business branding:",
        error,
      );

      setBranding(null);
      setLogoObjectUrl(null);
      setWatermarkObjectUrl(null);
    } finally {
      setLoading(false);
    }
  }, []);

  /*
   * Load branding when the provider mounts.
   */
  useEffect(() => {
    refreshBranding();
  }, [refreshBranding]);

  /*
   * Clean up browser object URLs when the provider
   * is removed from the page.
   */
  useEffect(() => {
    return () => {
      if (logoObjectUrl) {
        URL.revokeObjectURL(
          logoObjectUrl,
        );
      }

      if (watermarkObjectUrl) {
        URL.revokeObjectURL(
          watermarkObjectUrl,
        );
      }
    };
  }, [
    logoObjectUrl,
    watermarkObjectUrl,
  ]);

  return (
    <BrandingContext.Provider
      value={{
        branding,
        loading,
        logoObjectUrl,
        watermarkObjectUrl,
        refreshBranding,
      }}
    >
      {children}
    </BrandingContext.Provider>
  );
}

export function useBranding() {
  return useContext(
    BrandingContext,
  );
}
