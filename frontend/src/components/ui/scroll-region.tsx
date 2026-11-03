import type { ReactNode } from "react";
import { cn } from "@/lib/utils";

type Props = {
  /** Nom accessible du contenu défilant (en général la légende du tableau). */
  label: string;
  className?: string;
  children: ReactNode;
};

/**
 * Conteneur à défilement horizontal : un contenu plus large que l'écran défile au lieu d'être
 * tronqué (WCAG 1.4.10). Il est focusable et nommé pour que le défilement reste possible au
 * clavier (WCAG 2.1.1) ; l'anneau de focus suit la charte (2 px, `--ring`).
 */
export function ScrollRegion({ label, className, children }: Props) {
  return (
    <div
      role="group"
      aria-label={label}
      // eslint-disable-next-line jsx-a11y/no-noninteractive-tabindex -- conteneur défilant : accès clavier (WCAG 2.1.1)
      tabIndex={0}
      className={cn("overflow-x-auto focus-visible:outline-2 focus-visible:outline-ring", className)}
    >
      {children}
    </div>
  );
}
