import { T } from "../strings";
import Logo from "./Logo";

export default function Header() {
  return (
    <header className="app-header">
      <div className="app-brand">
        <Logo />
        <h1>
          Huqooq-e-Zan <span className="hq-ur" lang="ur">حقوقِ زن</span>
        </h1>
      </div>
      <p className="hq-ul" lang="ur">{T.tagline}</p>
      <p className="hq-en">{T.taglineEn}</p>
      <ul className="app-topics" aria-label="Topics covered">
        {T.topics.map((t) => (
          <li key={t.en} className="hq-chip"><span lang="ur">{t.ur}</span> · {t.en}</li>
        ))}
      </ul>
    </header>
  );
}
