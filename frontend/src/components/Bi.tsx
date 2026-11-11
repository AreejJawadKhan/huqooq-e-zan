/** Bilingual label: Urdu (rtl) above English (ltr), so mixed-direction text never reorders. */
export default function Bi({ ur, en, inline = false }: { ur: string; en: string; inline?: boolean }) {
  return (
    <span className={inline ? "bi bi-inline" : "bi"}>
      <span lang="ur" dir="rtl" className="bi-ur">{ur}</span>
      <span lang="en" dir="ltr" className="bi-en">{en}</span>
    </span>
  );
}
