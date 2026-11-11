# Huqooq-e-Zan (حقوقِ زن) design system

Voice-first, Urdu-first legal-information assistant for women in Pakistan. It must feel dignified, calm and trustworthy to someone who is stressed, on a phone and possibly reading Urdu aloud. Source of truth for values: `frontend/src/design/tokens.css` and `components.css`. This file explains how to use them. Published reference: the "Huqooq-e-Zan Design System" artifact in claude.ai.

## Brand
- Name: Huqooq-e-Zan in Latin script, حقوقِ زن in Urdu. Never shorten to "Huqooq" alone in the interface.
- Mark: speech bubble with three rising bars, third bar gold, violet tile. Do not recolour, rotate or add faces.
- Colour meaning: violet and gold echo the women's suffrage movement. Violet = action and identity. Gold = wage figures and dates. Red = danger only, never decorative.
- Voice: respectful, steady, never pitying. "Your rights", not "victims". Never promise outcomes.

## Content rules
- Urdu first, English beneath in muted text. Roman Urdu is accepted as input, never output.
- Short plain sentences. Say what the law says, then what to do next.
- Every legal claim has a citation chip (Act and section). Say "not found" rather than guess.
- No exclamation marks. Every answer ends with: legal information, not legal advice.
- Unverified numbers carry a visible "Not yet verified" label on the number itself.
- Privacy line under the question box: do not type name, address or phone number.

## Visual rules
- Warm paper background (`--surface-100`), violet `--brand`. Hero and letter button use `--brand-deep` to `--brand-deep-2` (light and dark values differ; use the variables).
- Light and dark themes via `data-theme` on `<html>`. Text at least 4.5:1 in both. Control borders use `--line`.
- Urdu answer 22 to 24px with line-height about 2.1. Nothing below 14px.
- `--radius-md` on controls, `--radius-lg` on cards. One soft shadow, light mode only.
- Touch targets at least 48px (`--touch`). Mic hero button is large and shows a label.
- Urdu blocks `dir="rtl"` with `--font-urdu`; English blocks `dir="ltr"`; phone numbers `dir="ltr"`.
- Focus ring: 2px `--focus`, offset 2px, on every interactive element.
- No new colours. Only CSS variables from `tokens.css`.

## Bilingual labels
Stack Urdu above English as two blocks (use the `Bi` component). Never join with a slash on one line: mixed-direction text reorders. Inline form is for chips only. The English toggle (`prefs.tsx`, localStorage `hq-english`) hides English everywhere.

## Icons
Few, always with a text label. Stroke 2px, round caps, current colour. No emoji, no pictures of people. Icons live in `src/components/Icons.tsx`.

## The four states (UI comes only from `response.status`)
| State | Header | Shows | Never shows |
| --- | --- | --- | --- |
| answered | info-bg | Urdu, English, citations, referrals, caveats, letter button | Claims without citations (zero citations = not_found) |
| not_found | caution-bg | Honest "not found", referrals | Guesses |
| out_of_scope | caution-bg | What the app covers, referrals | Legal claims |
| danger | danger-bg, `role="alert"` | Call 15 button first, then helplines | Legal text, citations, letter button |

## Accessibility
- Danger banner `role="alert"`; mic has `aria-label`; results in an `aria-live` region; `lang` on every language block.
- Meaning never by colour alone. Reduced motion is respected.
- Fonts: Noto Nastaliq Urdu (answers), Noto Naskh Arabic (small UI), Inter (Latin).

## Tokens added in the redesign
`--brand-deep`, `--brand-deep-2`, `--on-deep`, `--on-deep-muted` (hero band, letter call-to-action). Values are in `tokens.json` and `tokens.css`.
