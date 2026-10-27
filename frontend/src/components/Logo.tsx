import { cn } from "@/lib/utils";

/** Pictogramme : goutte et vague sur une tuile. Marque typographique propre au projet. */
export function LogoMark({ className, mono = false }: { className?: string; mono?: boolean }) {
  return (
    <svg
      className={cn("block shrink-0", className)}
      width="28"
      height="28"
      viewBox="0 0 28 28"
      aria-hidden="true"
      focusable="false"
    >
      <rect width="28" height="28" rx="6" className={mono ? "fill-foreground" : "fill-primary"} />
      <path
        className={mono ? "fill-surface" : "fill-primary-foreground"}
        d="M14 5.25c0 0-6.25 6.9-6.25 11.1a6.25 6.25 0 0 0 12.5 0C20.25 12.15 14 5.25 14 5.25Z"
      />
      <path
        className={mono ? "stroke-foreground" : "stroke-brand-accent"}
        fill="none"
        strokeWidth="1.6"
        strokeLinecap="round"
        d="M8.9 17.1c1.27-1.1 2.55-1.1 3.82 0s2.55 1.1 3.82 0 1.9-.85 2.55-.55"
      />
    </svg>
  );
}

/** Marque ONEA : pictogramme + mot-symbole ; `compact` n'affiche que le pictogramme. */
export function Logo({
  compact = false,
  subtitle,
  className,
}: {
  compact?: boolean;
  subtitle?: string;
  className?: string;
}) {
  return (
    <div className={cn("flex items-center gap-3", className)}>
      <LogoMark />
      {!compact && (
        <div className="flex min-w-0 flex-col leading-[1.15]">
          <span className="text-base font-bold tracking-[0.08em]">ONEA</span>
          {subtitle && <span className="mt-0.5 text-xs text-text-muted">{subtitle}</span>}
        </div>
      )}
    </div>
  );
}
