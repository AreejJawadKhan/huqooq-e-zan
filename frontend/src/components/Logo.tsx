/** Original mark: a speech bubble (voice) holding a rising bar of three strokes (rights stand up). */
export default function Logo({ size = 44 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 48 48" role="img" aria-label="Huqooq-e-Zan">
      <rect width="48" height="48" rx="14" fill="var(--brand)" />
      <path d="M12 14a4 4 0 0 1 4-4h16a4 4 0 0 1 4 4v12a4 4 0 0 1-4 4H22l-7 6v-6h-1a4 4 0 0 1-2-3.5Z" fill="var(--on-brand)" />
      <rect x="18" y="19" width="3" height="6" rx="1.5" fill="var(--brand)" />
      <rect x="23" y="16" width="3" height="9" rx="1.5" fill="var(--brand)" />
      <rect x="28" y="13" width="3" height="12" rx="1.5" fill="var(--accent)" />
    </svg>
  );
}
