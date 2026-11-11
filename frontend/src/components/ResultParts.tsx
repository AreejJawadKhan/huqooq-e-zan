import type { Caveat, Citation, Referral, WageInfo } from "../types";
import { T } from "../strings";
import Bi from "./Bi";

/** Only http(s) links are rendered; anything else (javascript:, data:) is dropped. */
export function safeUrl(u: string): string | null {
  try {
    const url = new URL(u);
    return url.protocol === "https:" || url.protocol === "http:" ? url.href : null;
  } catch {
    return null;
  }
}

/** Phone numbers may contain only digits, +, and spaces/dashes; otherwise no tel: link is made. */
export function telHref(n: string): string | null {
  return /^[0-9+\-\s()]{2,20}$/.test(n) ? `tel:${n.replace(/[^0-9+]/g, "")}` : null;
}

export function NotVerified() {
  return <span className="hq-chip" style={{ background: "var(--caution-bg)", color: "var(--caution-ink)" }}><Bi inline ur={T.notVerified} en={T.notVerifiedEn} /></span>;
}

export function CitationChip({ c }: { c: Citation }) {
  return (
    <details className="hq-cite">
      <summary><span className="hq-chip">{c.act}, s.{c.section}{c.heading ? ` (${c.heading})` : ""}</span></summary>
      <div className="hq-excerpt">{c.excerpt}</div>
      {safeUrl(c.source_url) && <a href={safeUrl(c.source_url)!} target="_blank" rel="noopener noreferrer">{T.source} / Source</a>}
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
      <h3 className="hq-section-title"><Bi ur={T.whereToGo} en="Where to go" /></h3>
      <ul className="hq-list">
        {items.map((r) => (
          <li key={r.name}>
            <div>
              <div className="hq-ref-name">{r.name}</div>
              {r.note && <p className="hq-ref-note">{r.note}</p>}
              {!r.verified && <NotVerified />}
            </div>
            {r.number && (telHref(r.number) ? (
              <a className="hq-btn ghost" href={telHref(r.number)!} aria-label={`${T.call} ${r.number}`}>
                <bdi dir="ltr" className="hq-ltr">{r.number}</bdi>
              </a>
            ) : (
              <bdi dir="ltr" className="hq-ltr">{r.number}</bdi>
            ))}
          </li>
        ))}
      </ul>
    </div>
  );
}
