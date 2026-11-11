import type { AskRequest, AskResult, Degraded, LetterRequest } from "./types";

/** A failed request. `code` is "rate_limited" for the per-client limit (HTTP 429); other failures have no code. */
export class ApiError extends Error {
  status: number;
  code: string;
  constructor(message: string, status: number, code = "") {
    super(message);
    this.status = status;
    this.code = code;
  }
}

async function apiError(res: Response): Promise<ApiError> {
  try {
    const body = await res.json();
    const detail = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail);
    return new ApiError(detail, res.status, typeof body.code === "string" ? body.code : "");
  } catch {
    return new ApiError(`${res.status} ${res.statusText}`, res.status);
  }
}

/** `?mock=1` serves the sample responses in public/fixtures so the UI works without a backend. */
export const MOCK = new URLSearchParams(window.location.search).get("mock") === "1";

const ROMAN_WORDS = /\b(mera|meri|mujhe|mere|nahi|nahin|kya|hai|hain|mein|kar|raha|rahe|tankhwah|zameen|bhai|hissa)\b/i;

function mockFixture(q: string): string {
  if (/danger|beat|hit me|kill|threat|suicide|خطر|مار|دھمک/i.test(q)) return "ask_danger";
  if (/busy|degraded/i.test(q)) return "ask_degraded";
  if (ROMAN_WORDS.test(q) && !/[\u0600-\u06ff]/.test(q)) return "ask_answered_roman";
  if (/wage|salary|pay|تنخواہ|اجرت/i.test(q)) return "ask_answered_wage";
  if (/property|inherit|land|share|جائیداد|زمین|وراثت|حصہ/i.test(q)) return "ask_answered_property";
  if (/province|which law/i.test(q)) return "ask_needs_province";
  if (/xyz/i.test(q)) return "ask_not_found";
  if (/cook|recipe|weather|football|کھانا/i.test(q)) return "ask_out_of_scope";
  return "ask_answered";
}

export async function ask(req: AskRequest): Promise<AskResult> {
  if (MOCK) {
    await new Promise((r) => setTimeout(r, 600));
    const fixture = mockFixture(req.question);
    const res = await fetch(`/fixtures/${fixture}.json`);
    const body: AskResult = await res.json();
    if (fixture === "ask_degraded") body.degraded = "busy";
    // "nocite" simulates an answer that arrived without citations (must render as not found).
    return /nocite/i.test(req.question) ? { ...body, citations: [] } : body;
  }
  const res = await fetch("/api/ask", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(req),
  });
  if (!res.ok) throw await apiError(res);
  const body: AskResult = await res.json();
  // The server always answers; this header says when the answer came from the law text alone (no model).
  const degraded = res.headers.get("X-Huqooq-Degraded");
  return degraded ? { ...body, degraded: degraded as Degraded } : body;
}

function save(blob: Blob, name: string) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = name;
  a.click();
  URL.revokeObjectURL(url);
}

/** Posts the form and triggers a browser download of the generated .docx letter. */
export async function downloadLetter(req: LetterRequest): Promise<void> {
  if (MOCK) {
    save(new Blob([`MOCK LETTER\n\n${JSON.stringify(req, null, 2)}`], { type: "text/plain" }), "huqooq_letter_mock.txt");
    return;
  }
  const res = await fetch("/api/letter", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(req),
  });
  if (!res.ok) throw await apiError(res);
  save(await res.blob(), `huqooq_${req.letter_type}.docx`);
}
