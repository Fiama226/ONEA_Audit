import type { components } from "@/api/schema";

type S = components["schemas"];

export type ProgrammeTravail = S["ProgrammeDeTravail"];
export type ProgrammeTravailInput = S["ProgrammeDeTravailRequest"];
export type SyntheseProgramme = S["SyntheseProgrammeTravail"];
export type InstantaneProgramme = S["InstantaneResume"];

export type TestPrevu = S["TestPrevu"];
export type TestPrevuInput = S["TestPrevuRequest"];

export type Fiche = S["FicheDeTestListe"];
export type FicheDetail = S["FicheDeTest"];
export type FicheInput = S["FicheDeTestRequest"];
export type StatutFiche = S["StatutFicheEnum"];
export type ConclusionTest = S["ConclusionTestEnum"];

export type Piece = S["PieceJustificative"];
export type PieceUpdate = S["PatchedPieceJustificativeRequest"];

/** Actions de transition d'une fiche (routes `/test-sheets/{id}/<action>/`). */
export type FicheAction = "submit" | "validate" | "return" | "reopen";
export type NatureTest = S["NatureTestEnum"];
export type MethodeSelection = S["MethodeSelectionEnum"];
