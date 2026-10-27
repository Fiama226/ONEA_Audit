import { TZDate } from "@date-fns/tz";
import { format } from "date-fns";

export const APP_TIME_ZONE = "Africa/Ouagadougou";

function inAppZone(iso: string): TZDate {
  return new TZDate(new Date(iso), APP_TIME_ZONE);
}

/** "2026-10-27T23:30:00Z" -> "27/10/2026" (heure d'Ouagadougou). */
export function formatDate(iso: string): string {
  return format(inAppZone(iso), "dd/MM/yyyy");
}

/** "2026-10-27T23:30:00Z" -> "27/10/2026 23:30" (heure d'Ouagadougou). */
export function formatDateTime(iso: string): string {
  return format(inAppZone(iso), "dd/MM/yyyy HH:mm");
}
