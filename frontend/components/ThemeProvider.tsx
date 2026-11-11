"use client";

import {
  createContext,
  useContext,
  useEffect,
  useState,
} from "react";

type Theme = "light" | "dark" | "system";

type UiStyle = "default" | "glass";

type ThemeContextType = {
  /** Look chosen by this person. Glass only shows on the business side. */
  uiStyle: UiStyle;
  setUiStyle: (style: UiStyle) => void;
  /** Set by the app shell: glass is offered to general businesses only. */
  setGlassAllowed: (allowed: boolean) => void;
  glassActive: boolean;
  theme: Theme;
  setTheme: (theme: Theme) => void;
  resolvedTheme: "light" | "dark";
};

const ThemeContext =
  createContext<ThemeContextType | undefined>(
    undefined,
  );

function getSystemTheme(): "light" | "dark" {
  if (typeof window === "undefined") {
    return "light";
  }

  return window.matchMedia(
    "(prefers-color-scheme: dark)",
  ).matches
    ? "dark"
    : "light";
}

export function ThemeProvider({
  children,
}: {
  children: React.ReactNode;
}) {
  const [theme, setThemeState] =
    useState<Theme>("system");

  const [resolvedTheme, setResolvedTheme] =
    useState<"light" | "dark">("light");

  const [uiStyle, setUiStyleState] = useState<UiStyle>("default");
  const [glassAllowed, setGlassAllowed] = useState(false);
  const glassActive = glassAllowed && uiStyle === "glass";

  useEffect(() => {
    try {
      if (localStorage.getItem("linda_ui_style") === "glass") {
        // eslint-disable-next-line react-hooks/set-state-in-effect
        setUiStyleState("glass");
      }
    } catch {
      /* storage unavailable: stay on the standard look */
    }
  }, []);

  useEffect(() => {
    const savedTheme =
      localStorage.getItem(
        "funeralos_theme",
      ) as Theme | null;

    if (
      savedTheme === "light" ||
      savedTheme === "dark" ||
      savedTheme === "system"
    ) {
      // This effect synchronizes React state with the persisted
      // preference after hydration; keep the update intentional.
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setThemeState(savedTheme);
    }
  }, []);

  useEffect(() => {
    function applyTheme() {
      // The glass look is built on a dark scene, so it always runs dark.
      const nextTheme: "light" | "dark" = glassActive
        ? "dark"
        : theme === "system"
          ? getSystemTheme()
          : theme;

      setResolvedTheme(nextTheme);

      const root =
        document.documentElement;

      root.classList.toggle(
        "dark",
        nextTheme === "dark",
      );

      root.dataset.theme =
        nextTheme;

      if (glassActive) {
        root.dataset.ui = "glass";
      } else {
        delete root.dataset.ui;
      }

      root.style.colorScheme =
        nextTheme;
    }

    applyTheme();

    if (theme !== "system" || glassActive) {
      return;
    }

    const mediaQuery =
      window.matchMedia(
        "(prefers-color-scheme: dark)",
      );

    const handleChange = () => {
      applyTheme();
    };

    mediaQuery.addEventListener(
      "change",
      handleChange,
    );

    return () => {
      mediaQuery.removeEventListener(
        "change",
        handleChange,
      );
    };
  }, [theme, glassActive]);

  function setUiStyle(next: UiStyle) {
    setUiStyleState(next);

    try {
      localStorage.setItem("linda_ui_style", next);
    } catch {
      /* ignore */
    }
  }

  function setTheme(nextTheme: Theme) {
    setThemeState(nextTheme);

    localStorage.setItem(
      "funeralos_theme",
      nextTheme,
    );
  }

  return (
    <ThemeContext.Provider
      value={{
        uiStyle,
        setUiStyle,
        setGlassAllowed,
        glassActive,
        theme,
        setTheme,
        resolvedTheme,
      }}
    >
      {children}
    </ThemeContext.Provider>
  );
}

export function useTheme() {
  const context =
    useContext(ThemeContext);

  if (!context) {
    throw new Error(
      "useTheme must be used inside ThemeProvider",
    );
  }

  return context;
}