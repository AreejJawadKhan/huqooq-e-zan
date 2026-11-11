import type { Caveat, Citation, Referral, WageInfo } from "../types";
import { T } from "../strings";

export function NotVerified() {
  return <span className="hq-chip" style={{ background: "var(--caution-bg)", color: "var(--caution-ink)" }}>{T.notVerifiedEn} · {T.notVerified}</span>;
}

export function CitationChip({ c }: { c: Citation }) {
  return (
    <details className="hq-cite">
      <summary><span className="hq-chip">{c.act}, s.{c.section}{c.heading ? ` (${c.heading})` : ""}</span></summary>
      <div className="hq-excerpt">{c.excerpt}</div>
      {c.source_url && <a href={c.source_url} target="_blank" rel="noreferrer">{T.source} / Source</a>}
    </details>
  );
}

export function CaveatNote({ c }: { c: Caveat }) {
  return (
    <div className="hq-notice caution">
      <div lang="ur" dir="rtl" className="hq-ul">{c.ur}</div>
      <div>{c.en}</div>
    </div>
  );
}

export function WageChip({ w }: { w: WageInfo }) {
  return (
    <div className="hq-wage">
      <span style={{ textTransform: "capitalize", font: "600 14px var(--font-sans)" }}>{w.jurisdiction}</span>
      <b>{w.monthly_pkr != null ? `Rs ${w.monthly_pkr.toLocaleString("en-US")}` : "—"} <small style={{ font: "400 14px var(--font-sans)" }}>/ month</small></b>
      <span className="hq-ref-note">{T.asOf} / as of {w.as_of}{w.note ? ` · ${w.note}` : ""}</span>
      {!w.verified && <NotVerified />}
    </div>
  );
}

export function ReferralList({ items }: { items: Referral[] }) {
  if (items.length === 0) return null;
  return (
    <div>
      <h3 className="hq-section-title"><span lang="ur">{T.whereToGo}</span> / Where to go</h3>
      <ul className="hq-list">
        {items.map((r) => (
          <li key={r.name}>
            <div>
              <div className="hq-ref-name">{r.name}</div>
              {r.note && <p className="hq-ref-note">{r.note}</p>}
              {!r.verified && <NotVerified />}
            </div>
            {r.number && (
              <a className="hq-btn ghost" href={`tel:${r.number.replace(/\s/g, "")}`} aria-label={`${T.call} ${r.number}`}>
                <bdi dir="ltr" className="hq-ltr">{r.number}</bdi>
              </a>
            )}
          </li>
        ))}
      </ul>
    </div>
  );
}
