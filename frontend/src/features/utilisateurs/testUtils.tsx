import type { components } from "@/api/schema";
import type { DroitsGestionComptes, Me, Role } from "@/auth/types";
import { appRoutes } from "@/routes";
import { renderRoutes } from "@/test/shell";
import type {
  ActionsCompte,
  CompteUtilisateur,
  CompteUtilisateurListe,
  Delegation,
  MotDePasseTemporaire,
  RapportImport,
} from "./types";

type S = components["schemas"];

/** Rend l'application complète sur `path` pour un rôle donné (et un profil `me` complété). */
export function renderAdministration(path: string, role: Role = "ADMIN", me: Partial<Me> = {}) {
  return renderRoutes(appRoutes, role, { path, me });
}

/** Droits délégués d'un agent non administrateur (aucun par défaut). */
export function rights(overrides: Partial<DroitsGestionComptes> = {}): DroitsGestionComptes {
  return { creer: false, reinitialiser: false, roles: false, desactiver: false, ...overrides };
}

/** Toutes les actions permises (administrateur sur un compte actif d'un autre agent). */
export const ALL_ACTIONS: ActionsCompte = {
  modifier_profil: true,
  desactiver: true,
  reactiver: false,
  reinitialiser_mot_de_passe: true,
  desactiver_otp: false,
  modifier_courriel: true,
  modifier_direction: true,
  changer_role: true,
};

/** Aucune action permise (ex. délégué sans droit sur ce compte). */
export const NO_ACTIONS: ActionsCompte = {
  modifier_profil: false,
  desactiver: false,
  reactiver: false,
  reinitialiser_mot_de_passe: false,
  desactiver_otp: false,
  modifier_courriel: false,
  modifier_direction: false,
  changer_role: false,
};

/** Compte complet, au format de `CompteUtilisateurSerializer` (backend). */
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
    is_active: true,
    origine: "ADMINISTRATION",
    en_attente_connexion: true,
    date_joined: "2026-10-28T08:00:00Z",
    first_name: "Landry",
    last_name: "Kabore",
    premiere_connexion_le: null,
    desactive_le: null,
    desactive_par: null,
    motif_desactivation: "",
    doit_changer_mot_de_passe: true,
    mot_de_passe_expire_le: "2026-10-31T08:00:00Z",
    verrouille_jusqu_a: null,
    otp_connexion_actif: false,
    actions: ALL_ACTIONS,
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
    date_joined: "2026-10-28T08:00:00Z",
    ...overrides,
  } satisfies S["CompteUtilisateurListe"];
}

/** Rapport d'import, au format de `RapportImportSerializer` (backend). */
export function aReport(overrides: Partial<RapportImport> = {}): RapportImport {
  return {
    dry_run: true,
    crees: ["a.b"],
    ignores: [
      {
        ligne: 3,
        identifiant: "chef",
        motif: "Le rôle Administrateur ne peut pas être attribué par import.",
      },
    ],
    fichier_mots_de_passe_id: null,
    ...overrides,
  } satisfies S["RapportImport"];
}

/** Réponse d'une création ou d'une réinitialisation (`MotDePasseTemporaireSerializer`). */
export function aTemporaryPassword(
  overrides: Partial<MotDePasseTemporaire> = {},
): MotDePasseTemporaire {
  return {
    compte: anAccount(),
    courriel_envoye: false,
    mot_de_passe_temporaire: "Tmp-9f3K-q7Lm-2xWz",
    ...overrides,
  } satisfies S["MotDePasseTemporaire"];
}

/** Délégation (`DelegationGestionComptesSerializer`) : aucune par défaut. */
export function aDelegation(overrides: Partial<Delegation> = {}): Delegation {
  return {
    creer: false,
    reinitialiser: false,
    roles: false,
    desactiver: false,
    accorde_par: null,
    accorde_le: null,
    ...overrides,
  } satisfies S["DelegationGestionComptes"];
}
