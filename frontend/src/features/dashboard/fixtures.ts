import type { components } from "@/api/schema";

type S = components["schemas"];

/** Fixtures typées : recopiées de `backend/tests/tableaux_de_bord/contrat_lot8.json` (lot 8 T11). */
export const tauxFixture = {
  cloturees: 4,
  abandonnees: 1,
  total: 10,
  taux: 0.4,
  echues: 5,
  cloturees_echues: 3,
  taux_echues: 0.6,
} satisfies S["Taux"];

export const tableauRaiFixture = {
  annee: 2026,
  missions_par_statut: [{ statut: "EN_SUIVI", libelle: "En suivi", phase: "SUIVI", nombre: 2 }],
  missions_en_retard: [],
  etapes_en_retard: 0,
  jalons_a_valider: [],
  actions_par_direction: [
    {
      direction_id: "88888888-8888-4888-8888-888888888888",
      code: "DAF",
      libelle: "Direction administrative",
      cloturees: 4,
      ouvertes_dans_les_delais: 3,
      en_retard: 2,
      abandonnees: 1,
    },
  ],
  file_decisions: {
    a_cloturer: 1,
    abandons_proposes: 0,
    reports_en_attente: 1,
    missions_a_cloturer: 0,
    relances_en_echec: 0,
    relances_sans_adresse: 0,
  },
  cartographie: {
    version_id: "cccccccc-0000-4000-8000-cccccccccccc",
    annee: 2026,
    cellules: [{ probabilite: 3, impact: 4, nombre: 2 }],
  },
  taux: tauxFixture,
} satisfies S["TableauRai"];

export const tableauDgFixture = {
  annee: 2026,
  rapports_diffuses: [
    {
      mission_id: "11111111-1111-4111-8111-111111111111",
      reference: "MI-2026-001",
      titre: "Audit des achats",
      statut: "EN_SUIVI",
      nombre_actions: 5,
      actions_cloturees: 2,
    },
  ],
  taux: tauxFixture,
  taux_par_direction: [
    {
      ...tauxFixture,
      direction_id: "88888888-8888-4888-8888-888888888888",
      code: "DAF",
      libelle: "Direction administrative",
    },
  ],
  risques_eleves: {
    couverts: 1,
    non_couverts: 1,
    risques: [
      {
        id: "dddddddd-0000-4000-8000-dddddddddddd",
        code: "R-01",
        libelle: "Fraude aux achats",
        processus_code: "ACH",
        couvert: true,
        missions: ["MI-2026-001"],
      },
    ],
  },
} satisfies S["TableauDg"];

export const tableauAuditeurFixture = {
  mes_missions: [
    {
      mission_id: "11111111-1111-4111-8111-111111111111",
      reference: "MI-2026-001",
      titre: "Audit des achats",
      statut: "EN_SUIVI",
      date_fin_prevue: null,
    },
  ],
  mes_etapes_en_cours: [],
  mes_tests_a_documenter: [],
  actions_a_verifier: [
    {
      suivi_id: "55555555-5555-4555-8555-555555555555",
      mission_id: "11111111-1111-4111-8111-111111111111",
      reference: "MI-2026-001",
      libelle: "Formaliser le rapprochement mensuel",
      declaree_le: "2026-10-29T09:00:00Z",
    },
  ],
} satisfies S["TableauAuditeur"];

export const tableauAuditeFixture = {
  constats_a_repondre: [],
  mes_actions: [
    {
      suivi_id: "55555555-5555-4555-8555-555555555555",
      mission_id: "11111111-1111-4111-8111-111111111111",
      reference: "MI-2026-001",
      libelle: "Formaliser le rapprochement mensuel",
      statut: "EN_COURS",
      echeance: "2026-10-27",
      en_retard: true,
      jours_retard: 3,
    },
  ],
  mes_demandes_report: [],
} satisfies S["TableauAudite"];
