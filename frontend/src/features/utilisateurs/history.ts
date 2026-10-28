import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { apiFetch } from "@/api/client";
import { toQuery } from "@/api/query";
import type { components } from "@/api/schema";
import { fr } from "@/i18n/fr";

type S = components["schemas"];
type AuditLog = S["AuditLog"];

/** Doit rester égal au `PAGE_SIZE` DRF du backend (config/settings/base.py) : aucun page_size n'est envoyé. */
export const HISTORY_PAGE_SIZE = 25;

const M2M_OPERATIONS: Record<string, string> = {
  add: "Ajout",
  remove: "Retrait",
  clear: "Vidage",
  set: "Remplacement",
};
const EMPTY_VALUE = "—";

export const historyKey = (userId: number, page: number) =>
  ["utilisateurs", "history", userId, page] as const;

export function useUserHistory(userId: number, page: number) {
  return useQuery({
    queryKey: historyKey(userId, page),
    queryFn: () =>
      apiFetch<S["PaginatedAuditLogList"]>(
        `/api/v1/audit-log/${toQuery({ model: "users.user", object_id: userId, page })}`,
      ),
    placeholderData: keepPreviousData,
  });
}

export type ChangeLine = { field: string; label: string; before: string; after: string };

export const FIELD_LABELS: Record<string, string> = {
  first_name: "Prénom",
  last_name: "Nom",
  email: "E-mail",
  username: "Identifiant",
  role: "Rôle (annuaire)",
  role_provisoire: "Rôle provisoire",
  matricule: "Matricule",
  direction_code: "Direction",
  fonction: "Fonction",
  is_active: "Statut du compte",
  motif_desactivation: "Motif de désactivation",
  profil_gere_localement: "Profil géré dans la plateforme",
  keycloak_id: "Lien avec l'annuaire",
  origine: "Origine du compte",
  keycloak_sync_statut: "Synchronisation Keycloak",
  keycloak_sync_erreur: "Erreur de synchronisation Keycloak",
  is_staff: "Accès à l'administration technique",
  is_superuser: "Superutilisateur",
};

const HIDDEN_FIELDS = new Set([
  "id",
  "desactive_le",
  "desactive_par",
  "date_joined",
  "premiere_connexion_le",
  "keycloak_sync_le",
  "keycloak_sync_tentatives",
  "password",
  "last_login",
]);

const ENUM_VALUES: Record<string, Record<string, string>> = {
  role: fr.roles,
  role_provisoire: fr.roles,
  origine: { CONNEXION: "Première connexion", ANNUAIRE: "Import annuaire", CSV: "Import CSV" },
  keycloak_sync_statut: { A_JOUR: "À jour", EN_ATTENTE: "En attente", ECHEC: "Échec" },
  is_active: { True: "Actif", False: "Désactivé" },
};

const BOOLEAN_FIELDS = new Set(["profil_gere_localement", "is_staff", "is_superuser"]);

function formatValue(field: string, value: unknown): string {
  if (value === null || value === undefined) return EMPTY_VALUE;
  const text = typeof value === "string" ? value : JSON.stringify(value);
  if (text === "" || text === "None") return EMPTY_VALUE;
  if (BOOLEAN_FIELDS.has(field) && (text === "True" || text === "False")) {
    return text === "True" ? fr.common.yes : fr.common.no;
  }
  return ENUM_VALUES[field]?.[text] ?? text;
}

/** Traduit les changements bruts de django-auditlog en lignes lisibles (champs techniques masqués). */
export function describeChanges(entry: AuditLog): ChangeLine[] {
  const lines: ChangeLine[] = [];
  for (const [field, change] of Object.entries(entry.changes)) {
    if (HIDDEN_FIELDS.has(field)) continue;
    const label = FIELD_LABELS[field] ?? field;
    let before = EMPTY_VALUE;
    let after: string;
    if (Array.isArray(change)) {
      before = formatValue(field, change[0]);
      after = formatValue(field, change[1]);
    } else if ("type" in change) {
      after = `${M2M_OPERATIONS[change.operation] ?? change.operation} : ${change.objects.join(", ")}`;
    } else {
      after = formatValue(field, change.raw);
    }
    if (before === after) continue;
    lines.push({ field, label, before, after });
  }
  return lines;
}
