import type { Caveat, Citation, Referral, WageInfo } from "../types";
import { T } from "../strings";
import { En } from "../prefs";
import Bi from "./Bi";
import { IconAlert, IconDoc, IconInfo, IconPhone } from "./Icons";

/** Only http(s) links are rendered; anything else (javascript:, data:) is dropped. */
export function safeUrl(u: string): string | null {
  try {
    const url = new URL(u);
    return url.protocol === "https:" || url.protocol === "http:" ? url.href : null;
  } catch {
    return null;
  }
}

/** Phone numbers may contain only digits, +, spaces, dashes and brackets; otherwise no tel: link is made. */
export function telHref(n: string): string | null {
  return /^[0-9+\-\s()]{2,20}$/.test(n) ? `tel:${n.replace(/[^0-9+]/g, "")}` : null;
}

/** Real ingested headings can carry invisible direction marks, a trailing " ." or the start of the section body after a dash. */
export function cleanHeading(h: string): string {
  const head = h.replace(/[‎‏‪-‮]/g, "").split(/\s*(?:[–—]|--)\s*/)[0];
  const t = head.replace(/[-]/g, "").replace(/[\s.]+$/, "").trim();
  return t.length > 90 ? `${t.slice(0, 87).trimEnd()}…` : t;
}

export function NotVerified() {
  return <span className="hq-chip chip-caution"><Bi inline ur={T.notVerified} en={T.notVerifiedEn} /></span>;
}

export function StatusBar({ kind }: { kind: "answered" | "not_found" | "out_of_scope" | "danger" }) {
  const map = {
    answered: { cls: "ok", ur: T.statusAnswered, en: T.statusAnsweredEn, icon: <IconInfo /> },
    not_found: { cls: "warn", ur: T.statusNotFound, en: T.statusNotFoundEn, icon: <IconInfo /> },
    out_of_scope: { cls: "warn", ur: T.statusScope, en: T.statusScopeEn, icon: <IconInfo /> },
    danger: { cls: "danger", ur: T.statusDanger, en: T.statusDangerEn, icon: <IconAlert /> },
  }[kind];
  return (
    <div className={`status-bar ${map.cls}`}>
      {map.icon}
      <Bi inline ur={map.ur} en={map.en} />
    </div>
  );
}

export function CitationChip({ c }: { c: Citation }) {
  const href = safeUrl(c.source_url);
  return (
    <details className="hq-cite">
      <summary>
        <span className="hq-chip cite-chip"><IconDoc />{c.act}, s.{c.section}</span>
      </summary>
      <div className="hq-quote">
        {cleanHeading(c.heading) && <div className="hq-ref-name">s.{c.section}: {cleanHeading(c.heading)}</div>}
        <p className="hq-quote-label"><Bi inline ur={T.exactText} en={T.exactTextEn} /></p>
        <blockquote className="hq-excerpt" lang="en" dir="ltr">{c.excerpt}</blockquote>
        {href ? (
          <a href={href} target="_blank" rel="noopener noreferrer"><Bi inline ur={T.officialSource} en="Official source" /></a>
        ) : (
          <p className="hq-ref-note">Source link not available yet.</p>
        )}
      </div>
    </details>
  );
}

export function CaveatNote({ c }: { c: Caveat }) {
  return (
    <div className="hq-notice caution">
      <div lang="ur" dir="rtl" className="hq-ul">{c.ur}</div>
      <En as="div">{c.en}</En>
    </div>
  );
}

export function WageChip({ w }: { w: WageInfo }) {
  return (
    <div className="wage-card">
      <span className="wage-place">{w.jurisdiction}</span>
      <b className="wage-amount">{w.monthly_pkr != null ? `Rs ${w.monthly_pkr.toLocaleString("en-US")}` : "—"}</b>
      <span className="wage-unit" lang="ur" dir="rtl">{T.perMonth}</span>
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
      <ul className="ref-grid">
        {items.map((r) => {
          const href = r.number ? telHref(r.number) : null;
          return (
            <li key={r.name} className="ref-card">
              <div className="ref-body">
                <div className="hq-ref-name">{r.name}</div>
                {r.note && <p className="hq-ref-note">{r.note}</p>}
                {!r.verified && <NotVerified />}
              </div>
              {r.number && (href ? (
                <a className="hq-btn ref-call" href={href} aria-label={`${T.call} ${r.number}`}>
                  <IconPhone /><bdi dir="ltr" className="hq-ltr">{r.number}</bdi>
                </a>
              ) : (
                <bdi dir="ltr" className="hq-ltr ref-num">{r.number}</bdi>
              ))}
            </li>
          );
        })}
      </ul>
    </div>
  );
}
