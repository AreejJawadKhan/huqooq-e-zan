import { T } from "../strings";
import { En } from "../prefs";
import Bi from "./Bi";
import Logo from "./Logo";

export default function Footer() {
  return (
    <footer className="site-footer">
      <div className="footer-brand"><Logo size={36} /><span lang="ur" className="topbar-ur">حقوقِ زن</span><span lang="en" dir="ltr" className="topbar-en">Huqooq-e-Zan</span></div>
      <p className="hq-ul" lang="ur">{T.disclosure}</p>
      <En as="p" className="hq-en">{T.disclosureEn}</En>
      <details>
        <summary><Bi inline ur={T.limitsTitle} en={T.limitsTitleEn} /></summary>
        <ul className="hq-en" dir="ltr">{T.limits.map((l) => <li key={l}>{l}</li>)}</ul>
      </details>
      <p className="hq-hint" lang="en" dir="ltr">SDG 5 · SDG 8 · SDG 16 · Built for the Build with Google hackathon, GDGoC COMSATS Islamabad.</p>
    </footer>
  );
}
