import type { AskResponse, Jurisdiction } from "../types";
import { PROVINCES, T } from "../strings";
import Bi from "./Bi";
import { CaveatNote, CitationChip, ReferralList, WageChip } from "./ResultParts";

function Disclaimer({ r }: { r: AskResponse }) {
  return (
    <div>
      <p className="hq-ul" lang="ur">{r.disclaimer_ur}</p>
      <p className="hq-en">{r.disclaimer_en}</p>
    </div>
  );
}

function DangerBanner({ r }: { r: AskResponse }) {
  return (
    <div className="hq-stack">
      <div className="hq-banner" role="alert">
        <p className="hq-ur" lang="ur">{r.answer_ur}</p>
        <p className="hq-en">{r.answer_en}</p>
        <a className="hq-btn danger" href="tel:15"><Bi ur={T.call15} en={T.call15En} /></a>
      </div>
      <div className="hq-card wide"><ReferralList items={r.where_to_go.filter((x) => x.number !== "15")} /></div>
    </div>
  );
}

function Plain({ r, covers }: { r: AskResponse; covers: boolean }) {
  return (
    <div className="hq-card wide">
      <p className="hq-ur" lang="ur">{r.answer_ur || T.notFoundTitle}</p>
      <p className="hq-en">{r.answer_en || T.notFoundTitleEn}</p>
      {covers && (
        <div className="hq-notice caution">
          <div lang="ur" dir="rtl" className="hq-ul">{T.covers}</div>
          <div>{T.coversEn}</div>
        </div>
      )}
      <ReferralList items={r.where_to_go} />
      <Disclaimer r={r} />
    </div>
  );
}

export default function ResultView({
  r, onProvince, onLetter,
}: { r: AskResponse; onProvince: (j: Jurisdiction) => void; onLetter: () => void }) {
  if (r.status === "danger") return <DangerBanner r={r} />;
  if (r.status === "out_of_scope") return <Plain r={r} covers />;
  // An answer with no citation is never shown as an answer.
  if (r.status === "not_found" || r.citations.length === 0) return <Plain r={r} covers={false} />;

  return (
    <div className="hq-card wide">
      <p className="hq-ur" lang="ur">{r.answer_ur}</p>
      <p className="hq-en">{r.answer_en}</p>
      {r.caveats.map((c, i) => <CaveatNote key={i} c={c} />)}
      {r.wage && <WageChip w={r.wage} />}
      {r.needs_province && (
        <div className="hq-notice caution" role="group" aria-label="Province">
          <p style={{ margin: "0 0 8px" }}><Bi ur={T.provincePrompt} en={T.provincePromptEn} /></p>
          <div className="hq-chips">
            {PROVINCES.map((p) => (
              <button key={p.value} type="button" className="hq-chip-btn" onClick={() => onProvince(p.value)}>{p.ur} / {p.en}</button>
            ))}
          </div>
        </div>
      )}
      <div>
        <h3 className="hq-section-title"><Bi ur={T.legalBasis} en="Legal basis" /></h3>
        <div className="hq-stack">{r.citations.map((c) => <CitationChip key={c.chunk_id} c={c} />)}</div>
      </div>
      <ReferralList items={r.where_to_go} />
      {r.letter_type && (
        <button type="button" className="hq-btn" onClick={onLetter}><Bi ur={T.letter} en={T.letterEn} /></button>
      )}
      <Disclaimer r={r} />
    </div>
  );
}
