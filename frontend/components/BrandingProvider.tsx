
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
import { getToken } from "@/lib/auth";
import { applyBrandTheme, clearBrandTheme } from "@/lib/brandTheme";

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

const BrandingContext = createContext<BrandingContextType>({
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
      typeof window !== "undefined" ? getToken() : null;

    /*
     * No authenticated user means there is no
     * business whose branding we can load.
     */
    if (!token) {
      setBranding(null);
      setLogoObjectUrl(null);
      setWatermarkObjectUrl(null);
      clearBrandTheme();
      setLoading(false);
      return;
    }

    try {
      setLoading(true);

      /*
       * First get the authenticated user.
       */
      const meResponse = await api.get("/auth/me");
      const currentUser = meResponse.data;

      const businessId = currentUser?.business_id;

      if (!businessId) {
        console.error(
          "[Branding] No business_id found for authenticated user.",
        );

        setBranding(null);
        setLogoObjectUrl(null);
        setWatermarkObjectUrl(null);
        clearBrandTheme();

        return;
      }

      /*
       * Load the actual business.
       */
      const businessResponse = await api.get(
        `/businesses/${businessId}`,
      );

      const data = businessResponse.data;

      const brandingData: BrandingData = {
        name: data.name,
        logo_url: data.logo_url,
        watermark_url: data.watermark_url,
        primary_color: data.primary_color,
        secondary_color: data.secondary_color,
        watermark_opacity: data.watermark_opacity,
        theme_preference: data.theme_preference,
      };

      setBranding(brandingData);

      /*
       * Apply business colours globally.
       */
      applyBrandTheme(
        data.primary_color,
        data.secondary_color,
      );

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
       * The logo and watermark endpoints are protected.
       * Download through Axios so the authentication token
       * is included, then create browser object URLs.
       */

      /*
       * LOGO
       */
      if (data.logo_url) {
        try {
          const logoResponse = await api.get(
            data.logo_url,
            {
              responseType: "blob",
            },
          );

          const logoUrl = URL.createObjectURL(
            logoResponse.data,
          );

          setLogoObjectUrl(logoUrl);
        } catch (error) {
          console.error(
            "[Branding] Failed to load logo:",
            error,
          );

          // Preserve the previous working logo.
        }
      } else {
        // The business has deliberately removed its logo.
        setLogoObjectUrl(null);
      }

      /*
       * WATERMARK
       */
      if (data.watermark_url) {
        try {
          const watermarkResponse = await api.get(
            data.watermark_url,
            {
              responseType: "blob",
            },
          );

          const watermarkUrl = URL.createObjectURL(
            watermarkResponse.data,
          );

          setWatermarkObjectUrl(watermarkUrl);
        } catch (error) {
          console.error(
            "[Branding] Failed to load watermark:",
            error,
          );

          // Preserve the previous working watermark.
        }
      } else {
        // The business has deliberately removed its watermark.
        setWatermarkObjectUrl(null);
      }
    } catch (error) {
      console.error(
        "[Branding] Failed to load business branding:",
        error,
      );

      // Preserve the last successfully loaded branding
      // when a refresh fails temporarily.
    } finally {
      setLoading(false);
    }
  }, []);

  /*
   * Load branding when the user signs in.
   */
  useEffect(() => {
    const onSignedIn = () => {
      void refreshBranding();
    };

    window.addEventListener(
      "linda-signed-in",
      onSignedIn,
    );

    return () => {
      window.removeEventListener(
        "linda-signed-in",
        onSignedIn,
      );
    };
  }, [refreshBranding]);

  /*
   * Load branding when the provider mounts.
   */
  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void refreshBranding();
  }, [refreshBranding]);

  /*
   * Clean up the logo URL independently.
   */
  useEffect(() => {
    return () => {
      if (logoObjectUrl) {
        URL.revokeObjectURL(logoObjectUrl);
      }
    };
  }, [logoObjectUrl]);

  /*
   * Clean up the watermark URL independently.
   */
  useEffect(() => {
    return () => {
      if (watermarkObjectUrl) {
        URL.revokeObjectURL(watermarkObjectUrl);
      }
    };
  }, [watermarkObjectUrl]);

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
  return useContext(BrandingContext);
}
