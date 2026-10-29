import { TZDate } from "@date-fns/tz";
import { format } from "date-fns";
import { APP_TIME_ZONE } from "@/lib/dates";

/** ISO UTC -> valeur d'un champ `datetime-local` (heure d'Ouagadougou). */
export function toLocalInput(iso: string): string {
  return format(new TZDate(new Date(iso), APP_TIME_ZONE), "yyyy-MM-dd'T'HH:mm");
}

/**
 * Valeur d'un champ `datetime-local` -> ISO. Africa/Ouagadougou est à UTC+0 toute l'année
 * (pas d'heure d'été) : le décalage est donc fixe.
 */
export function fromLocalInput(local: string): string {
  return `${local}:00+00:00`;
}
