import { fr } from "@/i18n/fr";

const m = fr.missionEtapes;

/** « 12.50 » -> « 12,5 » ; `null` -> « — ». */
export function formatDays(value: string | null | undefined): string {
  if (value === null || value === undefined || value === "") return m.noValue;
  const n = Number(value);
  if (Number.isNaN(n)) return m.noValue;
  return n.toLocaleString("fr-FR", { maximumFractionDigits: 2 });
}

/** Écart en jours : positif = retard, négatif = avance, 0 = à l'heure, `null` = non calculable. */
export function formatGap(days: number | null): string {
  if (days === null) return m.noValue;
  if (days === 0) return m.gapOnTime;
  return days > 0
    ? m.gapLate.replace("{n}", String(days))
    : m.gapEarly.replace("{n}", String(-days));
}
