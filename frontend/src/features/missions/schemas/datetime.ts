import { TZDate } from "@date-fns/tz";
import { format } from "date-fns";
import { APP_TIME_ZONE } from "@/lib/dates";

/** ISO UTC -> valeur d'un champ `datetime-local` (heure d'Ouagadougou). */
export function toLocalInput(iso: string): string {
  return format(new TZDate(new Date(iso), APP_TIME_ZONE), "yyyy-MM-dd'T'HH:mm");
}

/**
 * Valeur d'un champ `datetime-local` (lue en heure d'Ouagadougou) -> ISO avec décalage
 * (`2026-03-02T09:00:00+00:00`). Le décalage est déduit de APP_TIME_ZONE : c'est l'inverse exact
 * de `toLocalInput`, et un changement de fuseau reste cohérent dans les deux sens.
 */
export function fromLocalInput(local: string): string {
  const [date = "", time = "00:00"] = local.split("T");
  const [y = 0, mo = 1, d = 1] = date.split("-").map(Number);
  const [h = 0, mi = 0] = time.split(":").map(Number);
  return format(new TZDate(y, mo - 1, d, h, mi, 0, APP_TIME_ZONE), "yyyy-MM-dd'T'HH:mm:ssxxx");
}
