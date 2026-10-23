export default function Logo({ size = 40 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 64 64" aria-label="Trazen Society">
      <defs><linearGradient id="lg" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stopColor="#8b5cf6" /><stop offset="1" stopColor="#22d3ee" /></linearGradient></defs>
      <rect x="4" y="4" width="56" height="56" rx="16" fill="#0a0a0f" stroke="url(#lg)" strokeWidth="3" />
      <path d="M18 20h28M32 20v26M22 46l10-8 10 8" fill="none" stroke="url(#lg)" strokeWidth="5" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}
