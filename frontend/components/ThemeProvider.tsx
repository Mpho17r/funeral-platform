"use client";

import {
  createContext,
  useCallback,
  useRef,
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
  /** Show a look without saving it yet (used while choosing). */
  previewUiStyle: (style: UiStyle) => void;
  /** Loads this person's saved look once we know who they are. */
  loadStyleFor: (userId: string | null) => void;
  /** True once this person has picked a look (or we've loaded their pick). */
  styleChosen: boolean;
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
  const [styleChosen, setStyleChosen] = useState(true);
  const userKey = useRef<string | null>(null);
  const glassActive = uiStyle === "glass";

  // Each person keeps their own look on this device. Someone who has never
  // chosen gets asked once, the first time they sign in.
  const loadStyleFor = useCallback((userId: string | null) => {
    userKey.current = userId;
    if (!userId) {
      setUiStyleState("default");
      setStyleChosen(true);
      return;
    }
    let saved: string | null = null;
    try {
      saved = localStorage.getItem(`linda_ui_style:${userId}`);
    } catch {
      /* storage unavailable */
    }
    setUiStyleState(saved === "glass" ? "glass" : "default");
    setStyleChosen(saved === "glass" || saved === "default");
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
    setStyleChosen(true);

    try {
      if (userKey.current) {
        localStorage.setItem(`linda_ui_style:${userKey.current}`, next);
      }
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
        previewUiStyle: setUiStyleState,
        loadStyleFor,
        styleChosen,
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