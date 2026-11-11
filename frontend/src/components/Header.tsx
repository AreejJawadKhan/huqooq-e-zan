import { T } from "../strings";
import { En } from "../prefs";

export default function Header() {
  return (
    <div className="hero-copy" id="top">
      <h1 className="hero-title" lang="ur">{T.heroTitle}</h1>
      <p className="hero-lead" lang="ur">{T.heroLead}</p>
      <En as="p" className="hero-lead-en">{T.heroLeadEn}</En>
      <ul className="hero-topics" aria-label="Topics covered">
        {T.topics.map((t) => <li key={t.en} className="hero-pill"><span lang="ur">{t.ur}</span><En> · {t.en}</En></li>)}
      </ul>
    </div>
  );
}
