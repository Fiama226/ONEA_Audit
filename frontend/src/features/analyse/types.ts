import type { components } from "@/api/schema";

type S = components["schemas"];

export type ReferentielAudit = S["ReferentielAudit"];
export type InstantaneReferentiel = S["InstantaneReferentiel"];
export type AvisAudite = S["AvisAudite"];
export type AvisInput = S["AvisRequestRequest"];
export type DroitsAnalyse = S["DroitsAnalyse"];

export type LigneMarc = S["LigneMARC"];
export type LigneMarcInput = S["LigneMARCRequest"];
export type ObjectifAudit = S["ObjectifAudit"];
export type ObjectifAuditInput = S["ObjectifAuditRequest"];
export type Questionnaire = S["Questionnaire"];
export type QuestionnaireInput = S["QuestionnaireRequest"];
export type Question = S["Question"];
export type QuestionInput = S["QuestionRequest"];
export type DescriptionProcessus = S["DescriptionProcessus"];
export type DescriptionProcessusInput = S["DescriptionProcessusRequest"];
export type GrilleSeparation = S["GrilleSeparation"];
export type GrilleSeparationInput = S["GrilleSeparationRequest"];
export type ForceFaiblesse = S["ForceFaiblesse"];
export type ForceFaiblesseInput = S["ForceFaiblesseRequest"];
export type RapportOrientation = S["RapportOrientation"];
export type RapportOrientationInput = S["PatchedRapportOrientationRequest"];

export type Appreciation = S["AppreciationEnum"];
export type CategorieObjectif = S["CategorieObjectifEnum"];
export type Composante = S["ComposanteEnum"];
export type CouvertureOrdre = S["CouvertureOrdreEnum"];
export type EvaluationConception = S["EvaluationConceptionEnum"];
export type MotifNonTest = S["MotifNonTestEnum"];
export type NatureControle = S["NatureControleEnum"];
export type RoleTache = S["RoleTacheEnum"];
export type StatutReferentiel = S["StatutReferentielEnum"];
export type TypeAvis = S["TypeAvisEnum"];
export type TypeForceFaiblesse = S["TypeForceFaiblesseEnum"];
export type TypeQuestionnaire = S["TypeQuestionnaireEnum"];
export type TypologieProcessus = S["TypologieProcessusEnum"];
export type VarianteOrientation = S["VarianteOrientationEnum"];
