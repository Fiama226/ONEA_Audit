import { ROLES } from "@/auth/types";
import { fr } from "@/i18n/fr";
import type { OrigineCompte, Role } from "./types";

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

/** Rôles qu'un délégué peut attribuer ; seul un administrateur attribue les autres (ADMIN, RAI, DG). */
const DELEGATE_ROLES: readonly Role[] = ["AUDITEUR", "AUDITE"];

/** Rôles proposés dans un sélecteur : un délégué donne AUDITEUR ou AUDITE seulement. */
export function assignableRoles(isAdmin: boolean): Role[] {
  return ROLES.filter((role) => isAdmin || DELEGATE_ROLES.includes(role));
}

/** « DAI — Département Audit Interne » ; code absent du référentiel ; ou « Non renseignée ». */
export function directionLabel(code: string, libelle: string | null | undefined): string {
  if (code === "") return "Non renseignée";
  if (!libelle) return `${code} (inconnue du référentiel)`;
  return `${code} — ${libelle}`;
}
