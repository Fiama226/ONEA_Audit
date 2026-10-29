import type { components } from "@/api/schema";

type S = components["schemas"];

export type DocumentType = S["TypeDocument"];
export type Document = S["Document"];
export type DocumentListe = S["DocumentListe"];
export type DocumentVersion = S["DocumentVersion"];
export type DocumentDisponible = S["DocumentDisponible"];
export type Gabarit = S["GabaritDocument"];
export type FormatNumerotation = S["FormatNumerotation"];
export type FormatNumerotationInput = S["PatchedFormatNumerotationEcritureRequest"];
export type ApercuFormat = S["ApercuFormatRequest"];
export type ApercuNumero = S["ApercuNumero"];
export type Consultation = S["Consultation"];

export type StatutGeneration = S["StatutGenerationEnum"];
export type StatutPdf = S["StatutPdfEnum"];
export type StatutGabarit = S["StatutGabaritEnum"];
export type FormatFichier = "docx" | "pdf";

/** Champs de statut communs à la version complète et à son résumé. */
export type VersionStatus = Pick<DocumentVersion, "statut" | "statut_pdf">;
/** Version téléchargeable ; `peut_relancer_pdf` n'existe que sur la version complète. */
export type DownloadableVersion = VersionStatus &
  Pick<DocumentVersion, "id"> &
  Partial<Pick<DocumentVersion, "peut_relancer_pdf">>;
