import { useEffect, useState } from "react";
import { T } from "../strings";
import Bi from "./Bi";

type Mode = "ur" | "roman" | null;

function voiceFor(prefix: string): SpeechSynthesisVoice | null {
  if (typeof window === "undefined" || !("speechSynthesis" in window)) return null;
  return window.speechSynthesis.getVoices().find((v) => v.lang.toLowerCase().startsWith(prefix)) ?? null;
}

/** Indian English reads Roman Urdu far better than US or UK English does, so prefer it. */
function englishVoice(): SpeechSynthesisVoice | null {
  if (typeof window === "undefined" || !("speechSynthesis" in window)) return null;
  const voices = window.speechSynthesis.getVoices();
  return voices.find((v) => v.lang.toLowerCase().replace("_", "-") === "en-in") ?? voices.find((v) => v.lang.toLowerCase().startsWith("en")) ?? null;
}

function pickMode(hasRoman: boolean): Mode {
  if (voiceFor("ur")) return "ur";
  if (hasRoman && englishVoice()) return "roman";
  return null;
}

/**
 * Reads the answer aloud. With an Urdu voice it speaks the Urdu-script answer (which the server guarantees has no Latin
 * letters, so it is read naturally). Without one, a person who wrote Roman Urdu hears the Roman Urdu answer through an
 * English voice (Indian English if there is one). Hidden when neither is possible.
 */
export default function SpeakButton({ text, roman = "" }: { text: string; roman?: string }) {
  const [mode, setMode] = useState<Mode>(() => pickMode(!!roman));
  const [speaking, setSpeaking] = useState(false);

  useEffect(() => {
    if (!("speechSynthesis" in window)) return;
    const update = () => setMode(pickMode(!!roman));
    window.speechSynthesis.addEventListener("voiceschanged", update);
    update();
    return () => {
      window.speechSynthesis.removeEventListener("voiceschanged", update);
      window.speechSynthesis.cancel();
    };
  }, [roman]);

  if (!mode) return null;

  function toggle() {
    const synth = window.speechSynthesis;
    if (speaking) { synth.cancel(); setSpeaking(false); return; }
    const u = new SpeechSynthesisUtterance(mode === "ur" ? text : roman);
    if (mode === "ur") {
      u.lang = "ur-PK";
      u.voice = voiceFor("ur");
    } else {
      const v = englishVoice();
      u.lang = v?.lang ?? "en-IN";
      u.voice = v;
    }
    u.onend = () => setSpeaking(false);
    u.onerror = () => setSpeaking(false);
    setSpeaking(true);
    synth.speak(u);
  }

  return (
    <button type="button" className="hq-btn ghost speak-btn" aria-pressed={speaking} onClick={toggle}>
      <Bi inline ur={speaking ? T.stopListening : T.listen} en={speaking ? "Stop" : "Listen"} />
    </button>
  );
}
