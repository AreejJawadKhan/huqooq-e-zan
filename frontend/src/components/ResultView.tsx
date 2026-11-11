import type { AskResponse, Jurisdiction } from "../types";
import { PROVINCES, T } from "../strings";
import { En } from "../prefs";
import Bi from "./Bi";
import SpeakButton from "./SpeakButton";
import { IconDoc } from "./Icons";
import { CaveatNote, CitationChip, ReferralList, StatusBar, WageChip, groupCitations } from "./ResultParts";

function Disclaimer({ r }: { r: AskResponse }) {
  return (
    <div className="disclaimer">
      <p className="hq-ul" lang="ur">{r.disclaimer_ur}</p>
      <En as="p" className="hq-en">{r.disclaimer_en}</En>
    </div>
  );
}

function DangerBanner({ r }: { r: AskResponse }) {
  return (
    <div className="hq-stack result-in">
      <div className="hq-banner" role="alert">
        <StatusBar kind="danger" />
        <p className="hq-ur" lang="ur">{r.answer_ur}</p>
        <En as="p" className="hq-en">{r.answer_en}</En>
        <a className="hq-btn danger call-big" href="tel:15"><Bi inline ur={T.call15} en={T.call15En} /></a>
      </div>
      <div className="result-card">
        <ReferralList items={r.where_to_go.filter((x) => x.number !== "15")} />
        <Disclaimer r={r} />
      </div>
    </div>
  );
}

/** `uncited`: the model answered without a citation, so its text is never shown; the fixed message is used instead. */
function Plain({ r, kind, uncited = false }: { r: AskResponse; kind: "not_found" | "out_of_scope"; uncited?: boolean }) {
  return (
    <div className="result-card result-in">
      <StatusBar kind={kind} />
      <div className="result-body">
        <p className="hq-ur" lang="ur">{(!uncited && r.answer_ur) || T.notFoundTitle}</p>
        <En as="p" className="hq-en">{(!uncited && r.answer_en) || T.notFoundTitleEn}</En>
        {kind === "out_of_scope" && (
          <div className="hq-notice caution">
            <div lang="ur" dir="rtl" className="hq-ul">{T.covers}</div>
            <En as="div">{T.coversEn}</En>
          </div>
        )}
        <ReferralList items={r.where_to_go} />
        <Disclaimer r={r} />
      </div>
    </div>
  );
}

export default function ResultView({
  r, onProvince, onLetter,
}: { r: AskResponse; onProvince: (j: Jurisdiction) => void; onLetter: () => void }) {
  if (r.status === "danger") return <DangerBanner r={r} />;
  if (r.status === "out_of_scope") return <Plain r={r} kind="out_of_scope" />;
  // An answer with no citation is never shown as an answer.
  if (r.status === "not_found") return <Plain r={r} kind="not_found" />;
  if (r.citations.length === 0) return <Plain r={r} kind="not_found" uncited />;

  return (
    <div className="result-card result-in">
      <StatusBar kind="answered" />
      <div className="result-body">
        <p className="hq-ur answer-ur" lang="ur">{r.answer_ur}</p>
        <SpeakButton text={r.answer_ur} />
        <En as="p" className="hq-en answer-en">{r.answer_en}</En>
        {r.caveats.map((c, i) => <CaveatNote key={i} c={c} />)}
        {r.wage && <WageChip w={r.wage} />}
        {r.needs_province && (
          <div className="hq-notice caution" role="group" aria-label="Province">
            <p style={{ margin: "0 0 8px" }}><Bi ur={T.provincePrompt} en={T.provincePromptEn} /></p>
            <div className="hq-chips">
              {PROVINCES.map((p) => (
                <button key={p.value} type="button" className="hq-chip-btn" onClick={() => onProvince(p.value)}>{p.ur}<En> / {p.en}</En></button>
              ))}
            </div>
          </div>
        )}
        <div>
          <h3 className="hq-section-title"><Bi ur={T.basedOn} en={T.basedOnEn} /></h3>
          <div className="hq-stack">{groupCitations(r.citations).map((c) => <CitationChip key={c.chunk_id} c={c} />)}</div>
        </div>
        <ReferralList items={r.where_to_go} />
        {r.letter_type && (
          <button type="button" className="letter-cta" onClick={onLetter}>
            <span className="letter-cta-icon"><IconDoc /></span>
            <Bi ur={T.letter} en={T.letterEn} />
          </button>
        )}
        <Disclaimer r={r} />
      </div>
    </div>
  );
}
