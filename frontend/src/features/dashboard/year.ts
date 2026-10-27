import { fr } from "@/i18n/fr";

/** Année du programme annuel : année civile courante (Ouagadougou = UTC+0). */
export function currentYear(now: Date = new Date()): number {
  return now.getUTCFullYear();
}

/** « Programme 2026 » */
export function programmeLabel(now: Date = new Date()): string {
  return `${fr.dashboard.programme} ${currentYear(now)}`;
}
