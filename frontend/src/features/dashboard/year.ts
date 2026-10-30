import { useSearchParams } from "react-router-dom";
import { fr } from "@/i18n/fr";

/** Année du programme annuel : année civile courante (Ouagadougou = UTC+0). */
export function currentYear(now: Date = new Date()): number {
  return now.getUTCFullYear();
}

/** « Programme 2026 » */
export function programmeLabel(now: Date = new Date()): string {
  return `${fr.dashboard.programme} ${currentYear(now)}`;
}

/** Années proposées par le sélecteur : les cinq dernières, l'année courante comprise, et la suivante. */
export function yearOptions(now: Date = new Date()): number[] {
  const year = currentYear(now);
  return Array.from({ length: 6 }, (_, i) => year + 1 - i);
}

/** Année choisie (paramètre d'adresse `annee`, valide ou non), année courante par défaut. */
export function useYearParam(): [number, (annee: number) => void] {
  const [params, setParams] = useSearchParams();
  const raw = Number(params.get("annee"));
  const annee = Number.isInteger(raw) && raw >= 2000 && raw <= 2100 ? raw : currentYear();
  const setAnnee = (value: number) =>
    setParams(
      (prev) => {
        const next = new URLSearchParams(prev);
        next.set("annee", String(value));
        return next;
      },
      { replace: true },
    );
  return [annee, setAnnee];
}
