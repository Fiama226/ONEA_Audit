import { http, HttpResponse, type RequestHandler } from "msw";
import { API_URL } from "@/test/msw";
import { MISSION_ID, pageOf, RECOMMANDATION_ID } from "./testUtils";
import type {
  AcceptationRisque,
  EngagementPlanActions,
  EtatEngagement,
  LigneRecommandation,
  SynthesePlan,
} from "./types";

export const RESPONSABLE = {
  id: 12,
  username: "fanta.sawadogo",
  nom_complet: "Fanta Sawadogo",
  role: "AUDITE",
  direction_code: "DAF",
  fonction: "Directrice financière",
} as const;

export const ACCEPTATION_ID = "eeeeeeee-5555-4555-8555-eeeeeeeeeeee";

export function aLigne(overrides: Partial<LigneRecommandation> = {}): LigneRecommandation {
  return {
    constat: "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
    reference: "C-01-0",
    libelle: "Formaliser le rapprochement mensuel",
    priorite: "HAUTE",
    statut_derive: "SANS_ACTION",
    nb_actions: 0,
    acceptation: null,
    ...overrides,
  };
}

export function aSummary(overrides: Partial<SynthesePlan> = {}): SynthesePlan {
  return {
    recommandations: [aLigne()],
    responsables: [],
    recommandations_sans_suite: [],
    actions_incompletes: [],
    engagements_manquants: [],
    ...overrides,
  };
}

/** Acceptation du risque, forme figée par le contrat du plan (`AcceptationRisque`). */
export function anAcceptance(overrides: Partial<AcceptationRisque> = {}): AcceptationRisque {
  return {
    id: ACCEPTATION_ID,
    recommandation: RECOMMANDATION_ID,
    justification: "Coût disproportionné.",
    auteur: RESPONSABLE,
    confirmation: {
      id: "ffffffff-ffff-4fff-8fff-ffffffffffff",
      type_document: "ACCEPTATION_RISQUE",
      signataire: { id: 12, nom_complet: "Fanta Sawadogo" },
      confirme_le: "2026-10-29T10:30:00Z",
      empreinte: "a".repeat(64),
    },
    texte: "Je soussignée Fanta Sawadogo accepte le risque.",
    ...overrides,
  } as AcceptationRisque;
}

export function anEngagement(): EngagementPlanActions {
  return {
    id: "99999999-9999-4999-8999-999999999999",
    mission: MISSION_ID,
    auteur: RESPONSABLE,
    confirmation: anAcceptance().confirmation,
    texte: "Je m'engage à réaliser mes actions.",
    empreinte_actions: "b".repeat(64),
  } as EngagementPlanActions;
}

type Options = {
  summary?: SynthesePlan;
  actions?: unknown[];
  acceptances?: AcceptationRisque[];
  etat?: EtatEngagement;
  nbActions?: number;
};

/** Handlers usuels du plan : synthèse, actions, acceptations, recommandations, engagement, annuaire. */
export function planHandlers({
  summary = aSummary(),
  actions = [],
  acceptances = [],
  etat = "NON_CONFIRME",
  nbActions = 1,
}: Options = {}): RequestHandler[] {
  const url = (path: string) => `${API_URL}/api/v1/${path}`;
  return [
    http.get(url("action-plans/summary/"), () => HttpResponse.json(summary)),
    http.get(url("corrective-actions/"), () => HttpResponse.json(pageOf(actions))),
    http.get(url("risk-acceptances/"), () => HttpResponse.json(pageOf(acceptances))),
    http.get(url("recommendations/"), () =>
      HttpResponse.json(
        pageOf([
          {
            id: RECOMMANDATION_ID,
            mission: MISSION_ID,
            constat: summary.recommandations[0]?.constat ?? "x",
            constat_reference: "C-01",
            libelle: "Formaliser le rapprochement mensuel",
            priorite: "HAUTE",
            ordre: 0,
          },
        ]),
      ),
    ),
    http.get(url("action-plan-commitments/texte/"), () =>
      HttpResponse.json({
        texte: "Je m'engage à réaliser les actions du plan d'actions qui me sont confiées.",
        nb_actions: nbActions,
        etat,
      }),
    ),
    http.get(url("action-plan-commitments/"), () => HttpResponse.json(pageOf([]))),
    http.get(url("users/"), () => HttpResponse.json(pageOf([RESPONSABLE]))),
    http.get(url("documents/available/"), () => HttpResponse.json([])),
  ];
}
