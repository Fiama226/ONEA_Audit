import type { components } from "@/api/schema";

type S = components["schemas"];

export type CompteUtilisateur = S["CompteUtilisateur"];
export type CompteUtilisateurListe = S["CompteUtilisateurListe"];
export type ActionsCompte = S["ActionsCompte"];
export type SyncKeycloak = S["SyncKeycloak"];
export type ProfilInput = S["PatchedProfilUtilisateurRequest"];
export type MotifDesactivationInput = S["MotifDesactivationRequest"];
export type EntreeAnnuaire = S["EntreeAnnuaire"];
export type ImportAnnuaireInput = S["ImportAnnuaireRequest"];
export type RapportImport = S["RapportImport"];
export type Role = S["RoleEnum"];
export type OrigineCompte = S["OrigineCompteEnum"];
export type KeycloakSyncStatut = S["KeycloakSyncStatutEnum"];
export type Direction = S["Direction"];

export type AccountAction = "deactivate" | "reactivate" | "resync-profile" | "retry-keycloak-sync";
