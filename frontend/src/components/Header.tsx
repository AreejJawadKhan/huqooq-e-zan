import { T } from "../strings";

export default function Header() {
  return (
    <header className="app-header">
      <h1>Huqooq <span className="hq-ur" lang="ur">حقوق</span></h1>
      <p className="hq-ul" lang="ur">{T.tagline}</p>
      <p className="hq-en">{T.taglineEn}</p>
    </header>
  );
}
