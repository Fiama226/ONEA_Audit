const DAYS = new Intl.NumberFormat("fr-FR", { maximumFractionDigits: 1 });

/** "20.0" -> "20", "12.5" -> "12,5" (charges en jours, décimales du serveur). */
export function formatDays(value: string | number): string {
  return DAYS.format(Number(value));
}
