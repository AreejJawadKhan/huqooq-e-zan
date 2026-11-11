// Cloudflare Pages Function: same-origin proxy from /api/* to the FastAPI backend (BACKEND_URL).
// Same origin means no CORS and the page's CSP (connect-src 'self') keeps working. The visitor's real IP is passed in a
// header that the backend only trusts when PROXY_SECRET matches, so clients cannot spoof it to dodge the rate limit.
export async function onRequest({ request, env }) {
  if (!env.BACKEND_URL) {
    return Response.json({ detail: "Backend is not configured." }, { status: 503 });
  }
  const url = new URL(request.url);
  const headers = new Headers(request.headers);
  for (const h of ["host", "cookie", "x-forwarded-for", "x-huqooq-client-ip", "x-huqooq-proxy-key"]) headers.delete(h);
  headers.set("x-huqooq-client-ip", request.headers.get("cf-connecting-ip") || "");
  if (env.PROXY_SECRET) headers.set("x-huqooq-proxy-key", env.PROXY_SECRET);
  const hasBody = !["GET", "HEAD"].includes(request.method);
  try {
    const res = await fetch(env.BACKEND_URL.replace(/\/$/, "") + url.pathname + url.search, {
      method: request.method,
      headers,
      body: hasBody ? request.body : undefined,
      redirect: "manual",
    });
    const out = new Headers(res.headers);
    out.delete("set-cookie");
    return new Response(res.body, { status: res.status, headers: out });
  } catch {
    return Response.json({ detail: "The answer service is temporarily unavailable. Please try again in a moment." }, { status: 502 });
  }
}
