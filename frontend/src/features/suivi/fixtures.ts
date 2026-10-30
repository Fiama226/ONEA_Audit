import type { components } from "@/api/schema";

type S = components["schemas"];

/** Fixtures typées du suivi : recopiées de `backend/tests/suivi/contrat_suivi.json` (lot 8 T10). */
export const MISSION_ID = "11111111-1111-4111-8111-111111111111";
export const SUIVI_ID = "55555555-5555-4555-8555-555555555555";
export const RECOMMANDATION_ID = "dddddddd-4444-4444-8444-dddddddddddd";
export const PREUVE_ID = "66666666-6666-4666-8666-666666666666";
export const REPORT_ID = "77777777-7777-4777-8777-777777777777";

export const responsableFixture = {
  id: 12,
  username: "fkone",
  nom_complet: "Fatou Koné",
  role: "AUDITE",
  direction_code: "DAF",
  fonction: "Chef de service",
} satisfies S["UtilisateurResume"];

export const missionSuiviFixture = {
  id: MISSION_ID,
  reference: "MI-2026-001",
  titre: "Audit des achats",
  statut: "EN_SUIVI",
} satisfies S["MissionSuivi"];

export const actionSuivieFixture = {
  id: SUIVI_ID,
  mission: missionSuiviFixture,
  constat: {
    id: "99999999-9999-4999-8999-999999999999",
    reference: "C-01",
    titre: "Écarts de stock",
  },
  recommandation: {
    id: RECOMMANDATION_ID,
    libelle: "Fiabiliser les inventaires",
    priorite: "HAUTE",
  },
  entite: {
    id: "88888888-8888-4888-8888-888888888888",
    code: "DAF",
    libelle: "Direction administrative",
  },
  action_libelle: "Formaliser le rapprochement mensuel",
  indicateur: "Rapprochements signés",
  responsable: responsableFixture,
  echeance_initiale: "2026-12-31",
  echeance: "2026-12-31",
  nombre_reports: 0,
  statut: "A_LANCER",
  en_retard: false,
  jours_retard: null,
  declaree_par: null,
  declaree_le: null,
  verifiee_par: null,
  verifiee_le: null,
  cloturee_par: null,
  cloturee_le: null,
  justification_abandon: "",
  motif_dernier_rejet: "",
  nombre_preuves: 0,
  demande_report_en_attente: null,
  derniere_activite_le: "2026-10-29T09:00:00Z",
  actions_possibles: ["start"],
} satisfies S["SuiviAction"];

export const recommandationSuivieFixture = {
  id: RECOMMANDATION_ID,
  mission: missionSuiviFixture,
  constat: actionSuivieFixture.constat,
  entite: actionSuivieFixture.entite,
  libelle: "Fiabiliser les inventaires",
  priorite: "HAUTE",
  statut_suivi: "A_LANCER",
  risque_accepte: false,
  actions_total: 1,
  actions_closes: 0,
  actions_en_retard: 0,
  prochaine_echeance: "2026-12-31",
} satisfies S["RecommandationSuivi"];

export const evenementFixture = {
  id: "aaaaaaaa-0000-4000-8000-aaaaaaaaaaaa",
  type: "OUVERT",
  par: null,
  pour_compte_de: null,
  le: "2026-10-29T09:00:00Z",
  statut_avant: "",
  statut_apres: "A_LANCER",
  texte: "",
} satisfies S["EvenementActionSuivi"];

export const preuveFixture = {
  id: PREUVE_ID,
  numero: 1,
  libelle: "Rapprochement d'octobre",
  description: "",
  nom_fichier_original: "rapprochement.pdf",
  taille_octets: 20480,
  type_mime: "application/pdf",
  empreinte_sha256: "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
  deposee_par: responsableFixture,
  deposee_le: "2026-10-29T10:00:00Z",
  actions_possibles: ["download", "remove"],
} satisfies S["Preuve"];

export const demandeReportFixture = {
  id: REPORT_ID,
  action: SUIVI_ID,
  echeance_actuelle: "2026-12-31",
  nouvelle_echeance: "2027-02-28",
  motif: "Délai de livraison du logiciel",
  statut: "EN_ATTENTE",
  demandee_par: responsableFixture,
  decidee_par: null,
  decidee_le: null,
  commentaire_decision: "",
  actions_possibles: ["accept", "refuse"],
} satisfies S["DemandeReport"];

export const missionACloturerFixture = {
  id: MISSION_ID,
  reference: "MI-2026-001",
  titre: "Audit des achats",
  statut: "EN_SUIVI",
  annee: 2026,
  actions_total: 3,
  actions_closes: 3,
} satisfies S["MissionACloturer"];

/** Enveloppe de liste paginée du serveur. */
export function pageOf<T>(results: T[]) {
  return { count: results.length, next: null, previous: null, results };
}
