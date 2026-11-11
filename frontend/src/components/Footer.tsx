import { T } from "../strings";
import Bi from "./Bi";

export default function Footer() {
  return (
    <footer className="hq-footer">
      <p className="hq-ul" lang="ur">{T.disclosure}</p>
      <p className="hq-en">{T.disclosureEn}</p>
      <details>
        <summary><Bi inline ur={T.limitsTitle} en={T.limitsTitleEn} /></summary>
        <ul className="hq-en">{T.limits.map((l) => <li key={l}>{l}</li>)}</ul>
      </details>
    </footer>
  );
}
