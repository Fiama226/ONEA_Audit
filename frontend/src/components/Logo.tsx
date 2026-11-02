import logoOnea from "@/assets/logo-onea.jpg";
import { cn } from "@/lib/utils";

/** Texte alternatif officiel du logo. */
export const LOGO_ALT = "ONEA — Office national de l'eau et de l'assainissement";

/**
 * Logo officiel ONEA (LOGO.jpg, fond blanc, carré). Posé sur une pastille blanche arrondie
 * pour rester lisible sur fond sombre. Taille pilotée par `className` (ex. `size-10`).
 */
export function LogoMark({ className }: { className?: string; mono?: boolean }) {
  return (
    <img
      src={logoOnea}
      alt={LOGO_ALT}
      width={500}
      height={500}
      decoding="async"
      className={cn("block size-10 shrink-0 rounded-md bg-white object-contain", className)}
    />
  );
}

/** Marque ONEA : logo officiel + sous-titre ; `compact` n'affiche que le logo. */
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
      {!compact && subtitle && (
        <span className="min-w-0 text-sm font-medium text-text-muted">{subtitle}</span>
      )}
    </div>
  );
}
