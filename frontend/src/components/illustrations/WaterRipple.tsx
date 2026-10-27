/** Illustration décorative de l'état vide : goutte et ondes concentriques (monochrome primaire). */
export function WaterRipple({ className }: { className?: string }) {
  const ring = "fill-none stroke-primary";
  return (
    <svg
      className={className}
      viewBox="0 0 320 176"
      aria-hidden="true"
      focusable="false"
      strokeWidth="1.25"
    >
      <ellipse cx="160" cy="138" rx="154" ry="30" className={ring} strokeOpacity="0.09" />
      <ellipse cx="160" cy="138" rx="116" ry="22.5" className={ring} strokeOpacity="0.18" />
      <ellipse cx="160" cy="138" rx="76" ry="15" className={ring} strokeOpacity="0.32" />
      <ellipse cx="160" cy="138" rx="36" ry="7" className={ring} strokeOpacity="0.5" />
      <path
        className="fill-surface stroke-primary"
        strokeWidth="1.5"
        d="M160 26c0 0-25 28.5-25 46.5a25 25 0 0 0 50 0C185 54.5 160 26 160 26Z"
      />
      <path
        className={ring}
        strokeOpacity="0.55"
        strokeLinecap="round"
        d="M141.5 78c4.6-3.9 9.2-3.9 13.8 0s9.2 3.9 13.8 0 7.6-3.1 10.4-1.9"
      />
      <path
        className={ring}
        strokeOpacity="0.35"
        strokeLinecap="round"
        d="M148.5 66.5c1.2-5.2 4-9.6 7.2-13.4"
      />
    </svg>
  );
}
