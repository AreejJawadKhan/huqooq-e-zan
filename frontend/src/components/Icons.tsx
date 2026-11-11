/** Small original line icons (stroke follows currentColor). Always used with a text label. */
const base = { width: 28, height: 28, viewBox: "0 0 24 24", fill: "none", stroke: "currentColor", strokeWidth: 1.8, strokeLinecap: "round", strokeLinejoin: "round", "aria-hidden": true } as const;

export const IconMic = ({ size = 32 }: { size?: number }) => (
  <svg {...base} width={size} height={size}><rect x="9" y="3" width="6" height="11" rx="3" /><path d="M5 11a7 7 0 0 0 14 0M12 18v3" /></svg>
);
export const IconShield = () => (
  <svg {...base}><path d="M12 3 5 6v5c0 4.5 3 8 7 10 4-2 7-5.5 7-10V6l-7-3Z" /><path d="M9 12l2 2 4-4" /></svg>
);
export const IconCoin = () => (
  <svg {...base}><circle cx="12" cy="12" r="8.5" /><path d="M9.5 9.5c.5-1 1.5-1.5 2.5-1.5 1.5 0 2.5.8 2.5 2s-1 1.7-2.5 2-2.5.8-2.5 2 1 2 2.5 2c1 0 2-.5 2.5-1.5M12 6.5V8m0 8v1.5" /></svg>
);
export const IconHome = () => (
  <svg {...base}><path d="M4 11 12 4l8 7" /><path d="M6 10v9h12v-9" /><path d="M10 19v-5h4v5" /></svg>
);
export const IconBook = () => (
  <svg {...base}><path d="M5 5a2 2 0 0 1 2-2h12v16H7a2 2 0 0 0-2 2V5Z" /><path d="M9 7h6M9 11h6" /></svg>
);
export const IconPhone = () => (
  <svg {...base}><path d="M6 3h3l1.5 4-2 1.5a11 11 0 0 0 5 5L15 11.5l4 1.5v3a2 2 0 0 1-2 2A13 13 0 0 1 4 5a2 2 0 0 1 2-2Z" /></svg>
);
export const IconDoc = () => (
  <svg {...base}><path d="M7 3h7l4 4v14H7V3Z" /><path d="M14 3v4h4M10 12h5M10 16h5" /></svg>
);
export const IconInfo = () => (
  <svg {...base}><circle cx="12" cy="12" r="9" /><path d="M12 11v5M12 8v.01" /></svg>
);
export const IconAlert = () => (
  <svg {...base}><path d="M12 3 2.5 20h19L12 3Z" /><path d="M12 10v4M12 17v.01" /></svg>
);
export const IconSun = () => (
  <svg {...base} width={22} height={22}><circle cx="12" cy="12" r="4" /><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4" /></svg>
);
export const IconMoon = () => (
  <svg {...base} width={22} height={22}><path d="M20 14.5A8 8 0 1 1 9.5 4 6.5 6.5 0 0 0 20 14.5Z" /></svg>
);
export const IconSpeaker = () => (
  <svg {...base} width={22} height={22}><path d="M4 9v6h4l5 4V5L8 9H4Z" /><path d="M16.5 9a4 4 0 0 1 0 6M18.5 6.5a7.5 7.5 0 0 1 0 11" /></svg>
);
