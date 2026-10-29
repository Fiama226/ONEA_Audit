import type { components } from "@/api/schema";
import type {
  DroitsAnalyse,
  LigneMarc,
  ObjectifAudit,
  Questionnaire,
  GrilleSeparation,
  ReferentielAudit,
} from "./types";

type S = components["schemas"];

export const ANALYSE_MISSION_ID = "11111111-1111-4111-8111-111111111111";

/** Droits d'analyse : tout à faux sauf les surcharges ; `satisfies` aligne la fabrique sur le schéma. */
export function analyseRights(partial: Partial<DroitsAnalyse> = {}): DroitsAnalyse {
  return {
    voir_travaux: false,
    contribuer_iii: false,
    contribuer_v: false,
    donner_avis: false,
    voir_referentiel: false,
    contribuer_vii: false,
    ...partial,
  } satisfies S["DroitsAnalyse"];
}

export function aMarcLine(overrides: Partial<LigneMarc> = {}): LigneMarc {
  return {
    id: "33333333-3333-4333-8333-333333333333",
    mission: ANALYSE_MISSION_ID,
    risque: "44444444-4444-4444-8444-444444444444",
    risque_code: "R-001",
    risque_libelle: "Fraude à la facturation",
    risque_niveau: "ELEVE",
    risque_score: 12,
    processus_code: "P-ACH",
    objet_auditable: null,
    objet_auditable_libelle: null,
    operation: "",
    objectif_controle: "",
    controle_attendu: "",
    controle_existant: "",
    composante: "",
    nature: "",
    evaluation: "",
    appreciation: null,
    cle: false,
    commentaire: "",
    ordre: 0,
    a_objectif: false,
    ...overrides,
  } satisfies LigneMarc;
}

export function aFramework(overrides: Partial<ReferentielAudit> = {}): ReferentielAudit {
  return {
    mission: ANALYSE_MISSION_ID,
    statut: "BROUILLON",
    statut_v: "A_FAIRE",
    statut_vi: "A_FAIRE",
    nb_lignes: 0,
    nb_forces: 0,
    nb_faiblesses: 0,
    risques_non_couverts: [],
    validation: null,
    validation_verifiee: false,
    avis: [],
    mes_droits: analyseRights({ voir_travaux: true, voir_referentiel: true }),
    ...overrides,
  } satisfies ReferentielAudit;
}

export function anObjective(overrides: Partial<ObjectifAudit> = {}): ObjectifAudit {
  return {
    id: "55555555-5555-4555-8555-555555555555",
    mission: ANALYSE_MISSION_ID,
    ligne_marc: "33333333-3333-4333-8333-333333333333",
    code: "OA-01",
    numero: 1,
    libelle: "",
    retenu: true,
    motif_non_test: "",
    justification: "",
    risque_code: "R-001",
    controle_existant: "",
    ...overrides,
  } satisfies ObjectifAudit;
}

export function aQuestionnaire(overrides: Partial<Questionnaire> = {}): Questionnaire {
  return {
    id: "66666666-6666-4666-8666-666666666666",
    mission: ANALYSE_MISSION_ID,
    type: "PRISE_CONNAISSANCE",
    processus: null,
    processus_code: null,
    titre: "Prise de connaissance",
    nb_questions: 0,
    nb_repondues: 0,
    etape_close: false,
    ...overrides,
  } satisfies Questionnaire;
}

export function aGrid(overrides: Partial<GrilleSeparation> = {}): GrilleSeparation {
  return {
    id: "77777777-7777-4777-8777-777777777777",
    mission: ANALYSE_MISSION_ID,
    processus: "88888888-8888-4888-8888-888888888888",
    processus_code: "P-ACH",
    taches: [],
    acteurs: [],
    cellules: [],
    commentaire: "",
    analyse: { taches_sans_acteur: [], taches_multi_executants: [], cumuls: [] },
    etape_close: false,
    ...overrides,
  } satisfies GrilleSeparation;
}
