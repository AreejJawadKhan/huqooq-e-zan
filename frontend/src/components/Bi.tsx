import { usePrefs } from "../prefs";

/** Bilingual label: Urdu (rtl) first, English (ltr) beneath or beside. English hides in Urdu-only mode. */
export default function Bi({ ur, en, inline = false }: { ur: string; en: string; inline?: boolean }) {
  const { showEnglish } = usePrefs();
  return (
    <span className={inline ? "bi bi-inline" : "bi"}>
      <span lang="ur" dir="rtl" className="bi-ur">{ur}</span>
      {showEnglish && <span lang="en" dir="ltr" className="bi-en">{en}</span>}
    </span>
  );
}
