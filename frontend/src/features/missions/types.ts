import type { components } from "@/api/schema";

type S = components["schemas"];

export type Mission = S["Mission"];
export type MissionListe = S["MissionListe"];
export type MissionInput = S["MissionRequest"];
export type DroitsMission = S["DroitsMission"];
export type Affectation = S["Affectation"];
export type AffectationInput = S["AffectationRequest"];
export type Declaration = S["Declaration"];
export type Etape = S["Etape"];
export type EtapeInput = S["PatchedEtapeRequest"];
export type FicheSuivi = S["FicheSuivi"];
export type Reunion = S["Reunion"];
export type ReunionInput = S["ReunionRequest"];
export type Entretien = S["Entretien"];
export type EntretienInput = S["EntretienRequest"];
export type RisqueMission = S["RisqueMission"];
export type RisqueMissionInput = S["RisqueMissionRequest"];
export type MatriceMission = S["MatriceMission"];
export type UtilisateurResume = S["UtilisateurResume"];

export type StatutMission = S["StatutMissionEnum"];
export type StatutEtape = S["StatutEtapeEnum"];
export type ActionEtape = S["ActionEtapeEnum"];
export type Phase = S["PhaseEnum"];
export type TypeMission = S["TypeMissionEnum"];
export type RoleMission = S["RoleMissionEnum"];
export type StatutDeclaration = S["StatutDeclarationEnum"];
export type StatutEntretien = S["StatutEntretienEnum"];
export type TypeReunion = S["TypeReunionEnum"];
export type EvenementDeclencheur = S["EvenementDeclencheurEnum"];
export type TypeEvenementEtape = S["TypeEvenementEtapeEnum"];
export type RoleEnum = S["RoleEnum"];
