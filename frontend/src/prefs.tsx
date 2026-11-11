import { createContext, useContext, useEffect, useState, type ReactNode } from "react";

type Theme = "light" | "dark";
export type MicLang = "ur-PK" | "en-IN";
interface Prefs { showEnglish: boolean; setShowEnglish: (v: boolean) => void; theme: Theme; setTheme: (t: Theme) => void; micLang: MicLang; setMicLang: (l: MicLang) => void }

const Ctx = createContext<Prefs>({ showEnglish: true, setShowEnglish: () => {}, theme: "light", setTheme: () => {}, micLang: "ur-PK", setMicLang: () => {} });
export const usePrefs = () => useContext(Ctx);

function read(key: string): string | null {
  try { return window.localStorage.getItem(key); } catch { return null; }
}
function write(key: string, v: string) {
  try { window.localStorage.setItem(key, v); } catch { /* storage unavailable: preference lasts for this visit only */ }
}

export function PrefsProvider({ children }: { children: ReactNode }) {
  const [showEnglish, setShowEnglishState] = useState(() => read("hq-english") !== "0");
  const [theme, setThemeState] = useState<Theme>(() => {
    const saved = read("hq-theme");
    if (saved === "light" || saved === "dark") return saved;
    return window.matchMedia?.("(prefers-color-scheme: dark)").matches ? "dark" : "light";
  });
  const [micLang, setMicLangState] = useState<MicLang>(() => (read("hq-miclang") === "en-IN" ? "en-IN" : "ur-PK"));
  useEffect(() => { document.documentElement.dataset.theme = theme; }, [theme]);
  return (
    <Ctx.Provider value={{
      showEnglish, theme, micLang,
      setMicLang: (l) => { setMicLangState(l); write("hq-miclang", l); },
      setShowEnglish: (v) => { setShowEnglishState(v); write("hq-english", v ? "1" : "0"); },
      setTheme: (t) => { setThemeState(t); write("hq-theme", t); },
    }}>{children}</Ctx.Provider>
  );
}

/** English helper text: hidden when the reader chose Urdu only. */
export function En({ children, as: Tag = "span", className = "" }: { children: ReactNode; as?: "span" | "p" | "div"; className?: string }) {
  const { showEnglish } = usePrefs();
  if (!showEnglish) return null;
  return <Tag className={className} lang="en" dir="ltr">{children}</Tag>;
}
