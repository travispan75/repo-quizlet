"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
} from "react";

type Theme = "light" | "dark";

type ThemeCtx = {
  theme: Theme;
  toggle: () => void;
};

const Ctx = createContext<ThemeCtx | null>(null);

const STORAGE_KEY = "theme";

export function ThemeProvider({ children }: { children: React.ReactNode }) {
  // Always start as "light" so SSR and the first client render agree. The FOUC
  // script already applied the real theme class to <html> before hydration, so
  // visible styling is correct. We sync local state to it post-mount below.
  const [theme, setTheme] = useState<Theme>("light");
  const firstRunRef = useRef(true);

  useEffect(() => {
    const root = document.documentElement;
    if (firstRunRef.current) {
      firstRunRef.current = false;
      const isDark = root.classList.contains("dark");
      if (isDark) setTheme("dark");
      return;
    }
    if (theme === "dark") root.classList.add("dark");
    else root.classList.remove("dark");
    try {
      localStorage.setItem(STORAGE_KEY, theme);
    } catch {}
  }, [theme]);

  const toggle = useCallback(() => {
    setTheme((t) => (t === "dark" ? "light" : "dark"));
  }, []);

  return <Ctx.Provider value={{ theme, toggle }}>{children}</Ctx.Provider>;
}

export function useTheme(): ThemeCtx {
  const v = useContext(Ctx);
  if (!v) throw new Error("useTheme must be used inside ThemeProvider");
  return v;
}

// Runs synchronously before React hydrates to prevent a flash of the wrong
// theme. Must mirror the resolution logic ThemeProvider uses on mount.
export const THEME_INIT_SCRIPT = `
(function() {
  try {
    var stored = localStorage.getItem('${STORAGE_KEY}');
    var prefers = window.matchMedia('(prefers-color-scheme: dark)').matches;
    var dark = stored ? stored === 'dark' : prefers;
    if (dark) document.documentElement.classList.add('dark');
  } catch (e) {}
})();
`;
