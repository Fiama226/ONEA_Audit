import type { components } from "@/api/schema";

type S = components["schemas"];

export type Rapport = S["Rapport"];
export type RapportDiffuse = S["RapportDiffuse"];
/** Lecture d'un rapport : version complète (équipe) ou diffusée (lecteurs). */
export type RapportLecture = S["RapportLecture"];
export type RapportModification = S["PatchedRapportModificationRequestRequest"];
export type StatutRapport = S["StatutRapportEnum"];
export type AppreciationGlobale = S["AppreciationGlobaleEnum"];
export type TexteValidation = S["TexteValidation"];
/** Signature PAdES du rapport final et résultat de sa vérification. */
export type SignatureRapport = S["SignatureElectronique"];

export type RapportProvisoire = S["RapportProvisoire"];
export type ConstatProvisoire = S["ConstatProvisoire"];
export type ReponseRapport = S["ReponseRapport"];
export type ReponseRapportInput = S["ReponseRapportRequestRequest"];
export type TexteReponseRapport = S["TexteReponseRapport"];

export type Destinataire = S["Destinataire"];
export type DestinataireInput = S["DestinataireCreationRequestRequest"];
export type DestinataireUpdate = S["PatchedDestinataireModificationRequestRequest"];
export type CategorieDestinataire = S["CategorieDestinataireEnum"];

/** Actions de transition d'un rapport (routes `/reports/{id}/<action>/`). */
export type RapportAction =
  "submit" | "validate" | "return" | "distribute" | "correct" | "acknowledge" | "sign";

/** Charge utile de chaque action : motif (renvoi, correction), message (diffusion), confirmation (validation). */
export type RapportActionPayload = {
  motif?: string;
  message?: string;
  confirme?: boolean;
  lieu?: string;
};

export type FormatRapport = "pdf" | "docx";
export type DocumentRapport = "rapport" | "note";
