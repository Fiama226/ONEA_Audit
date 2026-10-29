import type { components } from "@/api/schema";
import type { Role } from "@/auth/types";
import { appRoutes } from "@/routes";
import { renderRoutes } from "@/test/shell";
import type { CompteUtilisateur, CompteUtilisateurListe, RapportImport } from "./types";

type S = components["schemas"];

/** Rend l'application complète sur `path` pour un rôle donné. */
export function renderAdministration(path: string, role: Role = "ADMIN") {
  return renderRoutes(appRoutes, role, { path });
}

/** Compte complet : JSON gelé de `test_contrat_compte_utilisateur` (backend). */
export function anAccount(overrides: Partial<CompteUtilisateur> = {}): CompteUtilisateur {
  return {
    id: 7,
    username: "kabore.l",
    nom_complet: "Landry Kabore",
    email: "l.kabore@onea.bf",
    role: "AUDITEUR",
    direction_code: "",
    direction_libelle: null,
    fonction: "Auditeur",
    matricule: "M-042",
    is_active: false,
    origine: "CSV",
    en_attente_connexion: true,
    keycloak_sync_statut: "ECHEC",
    date_joined: "2026-10-28T08:00:00Z",
    first_name: "Landry",
    last_name: "Kabore",
    keycloak_lie: true,
    role_provisoire: true,
    premiere_connexion_le: null,
    profil_gere_localement: true,
    desactive_le: "2026-10-28T09:00:00Z",
    desactive_par: { id: 1, username: "admin", nom_complet: "Admin ONEA" },
    motif_desactivation: "Départ",
    keycloak_sync: {
      statut: "ECHEC",
      erreur: "Keycloak a refusé l'opération (HTTP 403).",
      derniere_tentative_le: "2026-10-28T09:00:01Z",
      tentatives: 1,
      manuel: true,
    },
    actions: {
      modifier_profil: true,
      desactiver: false,
      reactiver: true,
      resynchroniser_profil: true,
      relancer_synchro_keycloak: true,
    },
    ...overrides,
  } satisfies S["CompteUtilisateur"];
}

/** Ligne de liste : sous-ensemble de `anAccount`. */
export function aListAccount(
  overrides: Partial<CompteUtilisateurListe> = {},
): CompteUtilisateurListe {
  const { id, username, nom_complet, email, role, direction_code, direction_libelle } = anAccount();
  return {
    id,
    username,
    nom_complet,
    email,
    role,
    direction_code,
    direction_libelle,
    fonction: "Auditeur",
    matricule: "M-042",
    is_active: true,
    origine: "CSV",
    en_attente_connexion: false,
    keycloak_sync_statut: "A_JOUR",
    date_joined: "2026-10-28T08:00:00Z",
    ...overrides,
  } satisfies S["CompteUtilisateurListe"];
}

/** Rapport d'import : JSON gelé de `test_contrat_rapport_import` (backend). */
export function aReport(overrides: Partial<RapportImport> = {}): RapportImport {
  return {
    dry_run: true,
    crees: ["a.b"],
    mis_a_jour: [],
    ignores: [
      {
        ligne: 3,
        identifiant: "chef",
        motif: "Le rôle ADMIN ne s'attribue que dans l'annuaire (Keycloak).",
      },
    ],
    ...overrides,
  } satisfies S["RapportImport"];
}
