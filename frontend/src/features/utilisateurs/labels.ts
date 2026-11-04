import { fr } from "@/i18n/fr";
import type { KeycloakSyncStatut, OrigineCompte } from "./types";

export const ROLE_LABELS = fr.roles;

export const STATUS_LABELS = {
  actif: "Actif",
  inactif: "Désactivé",
  attente: "En attente de première connexion",
} as const;

export const ORIGINE_LABELS: Record<OrigineCompte, string> = {
  CONNEXION: "Première connexion",
  ANNUAIRE: "Import annuaire",
  CSV: "Import CSV",
  ADMINISTRATION: "Création par l'administration",
};

export const SYNC_LABELS: Record<KeycloakSyncStatut, string> = {
  A_JOUR: "À jour",
  EN_ATTENTE: "En attente",
  ECHEC: "Échec",
};

/** « DAI — Département Audit Interne » ; code absent du référentiel ; ou « Non renseignée ». */
export function directionLabel(code: string, libelle: string | null | undefined): string {
  if (code === "") return "Non renseignée";
  if (!libelle) return `${code} (inconnue du référentiel)`;
  return `${code} — ${libelle}`;
}
