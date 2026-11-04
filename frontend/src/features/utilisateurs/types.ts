import type { components } from "@/api/schema";

type S = components["schemas"];

export type CompteUtilisateur = S["CompteUtilisateur"];
export type CompteUtilisateurListe = S["CompteUtilisateurListe"];
export type ActionsCompte = S["ActionsCompte"];
export type ProfilInput = S["PatchedProfilUtilisateurRequest"];
export type MotifDesactivationInput = S["MotifDesactivationRequest"];
export type CreationCompteInput = S["CreationCompteRequest"];
export type MotDePasseTemporaire = S["MotDePasseTemporaire"];
export type Delegation = S["DelegationGestionComptes"];
export type DelegationInput = S["DelegationGestionComptesRequest"];
export type RapportImport = S["RapportImport"];
export type Role = S["RoleEnum"];
export type OrigineCompte = S["OrigineCompteEnum"];
export type Direction = S["Direction"];

export type AccountAction = "deactivate" | "reactivate" | "disable-otp";
