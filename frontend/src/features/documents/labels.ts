import type { StatutGabarit, StatutGeneration, StatutPdf } from "./types";

export const STATUT_GENERATION_LABELS: Record<StatutGeneration, string> = {
  EN_ATTENTE: "En attente",
  EN_COURS: "Génération en cours…",
  PRETE: "Prête",
  ECHEC: "Échec",
};

export const STATUT_PDF_LABELS: Record<StatutPdf, string> = {
  NON_DEMANDE: "PDF non demandé",
  EN_COURS: "PDF en cours…",
  PRET: "PDF prêt",
  ECHEC: "PDF indisponible",
};

/** Types de documents produits par les missions, pour les rôles sans accès à /document-types/. */
export const DOCUMENT_TYPE_LABELS: Record<string, string> = {
  ORDRE_MISSION: "Ordre de mission",
  PV_OUVERTURE: "PV de la réunion d'ouverture",
};

export const STATUT_GABARIT_LABELS: Record<StatutGabarit, string> = {
  DEPOSE: "Déposé",
  ACTIF: "Actif",
  ARCHIVE: "Archivé",
};

/** « v3 · provisoire » : numéro de version du gabarit et mention éventuelle. */
export function gabaritLabel(g: { version: number; provisoire: boolean }): string {
  return g.provisoire ? `v${g.version} · provisoire` : `v${g.version}`;
}

/** Génération ou PDF encore en traitement (déclenche l'interrogation périodique). */
export function isInProgress(v: { statut: StatutGeneration; statut_pdf: StatutPdf }): boolean {
  return (
    v.statut === "EN_ATTENTE" ||
    v.statut === "EN_COURS" ||
    (v.statut === "PRETE" && v.statut_pdf === "EN_COURS")
  );
}
