import { T } from "../strings";

export default function Footer() {
  return (
    <footer className="hq-footer">
      <p className="hq-ul" lang="ur">{T.disclosure}</p>
      <p className="hq-en">{T.disclosureEn}</p>
      <details>
        <summary><span lang="ur" dir="rtl">{T.limitsTitle}</span>&nbsp;/&nbsp;<span>{T.limitsTitleEn}</span></summary>
        <ul className="hq-en">{T.limits.map((l) => <li key={l}>{l}</li>)}</ul>
      </details>
    </footer>
  );
}
