import { STEPS, T, TOPIC_CARDS, TRUST } from "../strings";
import { En } from "../prefs";
import { IconBook, IconCoin, IconHome, IconMic, IconShield } from "./Icons";

const ICONS = { shield: IconShield, coin: IconCoin, home: IconHome } as const;

export function TopicCards({ onPick, disabled }: { onPick: (q: string) => void; disabled: boolean }) {
  return (
    <section className="sec" aria-labelledby="topics-h">
      <h2 id="topics-h" className="sec-title"><span lang="ur">{T.topicsTitle}</span><En className="sec-en">{T.topicsTitleEn}</En></h2>
      <div className="topic-grid">
        {TOPIC_CARDS.map((c) => {
          const Icon = ICONS[c.icon];
          return (
            <button key={c.key} type="button" className="topic-card" disabled={disabled} onClick={() => onPick(c.q)}>
              <span className="topic-icon"><Icon /></span>
              <span className="topic-ur" lang="ur" dir="rtl">{c.ur}</span>
              <En className="topic-en">{c.en}</En>
              <span className="topic-desc" lang="ur" dir="rtl">{c.descUr}</span>
              <En className="topic-desc-en">{c.descEn}</En>
              <span className="topic-go" lang="ur" dir="rtl">{T.askThis} ←</span>
            </button>
          );
        })}
      </div>
    </section>
  );
}

export function HowItWorks() {
  const icons = [IconMic, IconBook, IconShield];
  return (
    <section className="sec" aria-labelledby="how-h">
      <h2 id="how-h" className="sec-title"><span lang="ur">{T.howTitle}</span><En className="sec-en">{T.howTitleEn}</En></h2>
      <ol className="steps">
        {STEPS.map((s, i) => {
          const Icon = icons[i];
          return (
            <li key={s.en} className="step">
              <span className="step-num" aria-hidden="true">{["۱", "۲", "۳"][i]}</span>
              <span className="step-icon"><Icon /></span>
              <span className="step-ur" lang="ur" dir="rtl">{s.ur}</span>
              <En className="step-en">{s.en}</En>
            </li>
          );
        })}
      </ol>
    </section>
  );
}

export function TrustStrip() {
  return (
    <section className="trust" aria-label={T.trustTitle}>
      {TRUST.map((t) => (
        <div key={t.en} className="trust-item">
          <IconShield />
          <span className="trust-ur" lang="ur" dir="rtl">{t.ur}</span>
          <En className="trust-en">{t.en}</En>
        </div>
      ))}
    </section>
  );
}
