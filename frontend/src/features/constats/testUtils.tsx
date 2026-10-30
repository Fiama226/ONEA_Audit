import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render } from "@testing-library/react";
import { http, HttpResponse, type RequestHandler } from "msw";
import { createMemoryRouter, RouterProvider, type RouteObject } from "react-router-dom";
import { vi } from "vitest";
import type { Role } from "@/auth/types";
import { AuthContext } from "@/auth/useAuth";
import { aMission, MISSION_ID, pageOf } from "@/features/missions/testUtils";
import type { Mission } from "@/features/missions/types";
import { API_URL, server } from "@/test/msw";
import { allowSlowShell, authValueFor } from "@/test/shell";
import type { Constat, ReponseAudite } from "./types";

allowSlowShell();

export { MISSION_ID, pageOf };
export const CONSTAT_ID = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa";
export const ENTITE_ID = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb";
export const PROCESSUS_ID = "cccccccc-cccc-4ccc-8ccc-cccccccccccc";
export const FICHE_ID = "dddddddd-dddd-4ddd-8ddd-dddddddddddd";
const EMPREINTE = "9f2b7c1d4e5a60718293a4b5c6d7e8f90123456789abcdef0123456789abcdef";

const ENTITE = { id: ENTITE_ID, code: "DAF", libelle: "Direction administrative et financière" };
const PROCESSUS = { id: PROCESSUS_ID, code: "P-ACH", libelle: "Achats" };

/** Mission avec une entité et un processus : la création les préremplit. */
export function aConstatMission(overrides: Partial<Mission> = {}): Mission {
  return aMission({ entites_detail: [ENTITE], processus_detail: [PROCESSUS], ...overrides });
}

/** Réponse de l'audité en désaccord (forme figée par `test_api_contrat_lot6`). */
export function aReponse(overrides: Partial<ReponseAudite> = {}): ReponseAudite {
  return {
    id: "eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee",
    constat: CONSTAT_ID,
    cycle: 1,
    auteur: {
      id: 12,
      username: "fanta.sawadogo",
      nom_complet: "Fanta Sawadogo",
      role: "AUDITE",
      direction_code: "DAF",
      fonction: "Directrice financière",
    },
    position: "DESACCORD",
    commentaire: "Le contrôle existe.",
    confirmation: {
      id: "ffffffff-ffff-4fff-8fff-ffffffffffff",
      type_document: "REPONSE_CONSTAT",
      signataire: { id: 12, nom_complet: "Fanta Sawadogo" },
      confirme_le: "2026-10-29T10:30:00Z",
      empreinte: "a".repeat(64),
    },
    version_anterieure: false,
    texte: "Je confirme avoir pris connaissance du constat et être en désaccord.",
    ...overrides,
  } as ReponseAudite;
}

/** Constat soumis avec une réponse en désaccord (forme figée par `test_api_contrat_lot6`). */
export function aConstat(overrides: Partial<Constat> = {}): Constat {
  return {
    id: CONSTAT_ID,
    mission: MISSION_ID,
    reference: "C-01",
    titre: "Absence de rapprochement bancaire",
    statut: "SOUMIS",
    fiches: [FICHE_ID],
    fiches_detail: [{ id: FICHE_ID, test_code: "T-01", conclusion: "ANOMALIE" }],
    entite: ENTITE_ID,
    entite_detail: ENTITE,
    processus: PROCESSUS_ID,
    processus_detail: PROCESSUS,
    risque_mission: null,
    fait_constate: "Les rapprochements ne sont pas réalisés.",
    referentiel: "Procédure comptable, art. 4.",
    consequence: "Risque d'erreur non détectée.",
    conclusion: "Le contrôle est insuffisant.",
    probabilite: 3,
    impact: 5,
    score: 15,
    niveau: "ELEVE",
    causes: [
      {
        id: "11111111-aaaa-4aaa-8aaa-111111111111",
        categorie: "METHODES",
        description: "Pas de procédure écrite",
        ordre: 0,
      },
    ],
    recommandations: [
      {
        id: "22222222-bbbb-4bbb-8bbb-222222222222",
        libelle: "Formaliser le rapprochement mensuel",
        priorite: "HAUTE",
        ordre: 0,
      },
    ],
    cycle: 1,
    soumis_par: 3,
    soumis_le: "2026-10-28T08:00:00Z",
    validee_par: null,
    validee_le: null,
    motif_renvoi: null,
    empreinte_soumise: EMPREINTE,
    derniere_reponse: null,
    reponse_cycle_courant: false,
    texte_reponse: null,
    actions_possibles: [],
    ...overrides,
  } as Constat;
}

/** Constat vu par l'audité : champs internes nuls, texte de réponse fourni par le serveur. */
export function aConstatAudite(overrides: Partial<Constat> = {}): Constat {
  return aConstat({
    fiches_detail: null,
    motif_renvoi: null,
    risque_mission: null,
    texte_reponse: {
      accord: "Je suis en accord avec ce constat et je m'engage à le traiter.",
      desaccord: "Je suis en désaccord avec ce constat ; mon commentaire motive ma position.",
    },
    actions_possibles: ["REPONDRE"],
    ...overrides,
  });
}

export function aSheet(overrides: Record<string, unknown> = {}) {
  return {
    id: FICHE_ID,
    mission: MISSION_ID,
    test: "99999999-9999-4999-8999-999999999999",
    test_code: "T-01",
    test_libelle: "Rapprochements bancaires",
    objectif_code: "OA-01",
    statut: "VALIDE",
    conclusion: "ANOMALIE",
    resultat: "Aucun rapprochement en septembre.",
    constats: [],
    actions_possibles: [],
    ...overrides,
  };
}

type Options = {
  role?: Role;
  mission?: Mission;
  handlers?: RequestHandler[];
};

/** Handlers usuels : mission, fiches de test, constats et réponses. */
export function constatHandlers({
  mission = aConstatMission(),
  sheets = [aSheet()],
  constats = [] as Constat[],
  responses = [] as ReponseAudite[],
}: {
  mission?: Mission;
  sheets?: unknown[];
  constats?: Constat[];
  responses?: ReponseAudite[];
} = {}): RequestHandler[] {
  return [
    http.get(`${API_URL}/api/v1/missions/${mission.id}/`, () => HttpResponse.json(mission)),
    http.get(`${API_URL}/api/v1/mission-risks/`, () => HttpResponse.json(pageOf([]))),
    http.get(`${API_URL}/api/v1/test-sheets/`, () => HttpResponse.json(pageOf(sheets))),
    http.get(`${API_URL}/api/v1/findings/`, () => HttpResponse.json(pageOf(constats))),
    http.get(`${API_URL}/api/v1/findings/:id/`, ({ params }) => {
      const found = constats.find((c) => c.id === params.id);
      return found ? HttpResponse.json(found) : HttpResponse.json({ detail: "x" }, { status: 404 });
    }),
    http.get(`${API_URL}/api/v1/finding-responses/`, () => HttpResponse.json(pageOf(responses))),
  ];
}

/** Rend un ou plusieurs écrans sous `/missions/:id/...` pour un rôle donné. */
export function renderConstats(
  path: string,
  routes: RouteObject[],
  { role = "AUDITEUR", handlers = [] }: Options = {},
) {
  server.use(...handlers);
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  const router = createMemoryRouter(routes, { initialEntries: [path] });
  const utils = render(
    <QueryClientProvider client={client}>
      <AuthContext.Provider value={authValueFor(role, vi.fn())}>
        <RouterProvider router={router} />
      </AuthContext.Provider>
    </QueryClientProvider>,
  );
  return { ...utils, router, client };
}
