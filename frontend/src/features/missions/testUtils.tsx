import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render } from "@testing-library/react";
import { http, HttpResponse, type RequestHandler } from "msw";
import { createMemoryRouter, RouterProvider } from "react-router-dom";
import { vi } from "vitest";
import type { Me, Role } from "@/auth/types";
import { AuthContext } from "@/auth/useAuth";
import { API_URL, server } from "@/test/msw";
import { allowSlowShell, authValueFor } from "@/test/shell";
import { missionRoutes } from "./routes";
import type { DroitsMission, Etape, Mission } from "./types";

// Les écrans de mission montent l'en-tête, les onglets et des dialogues : lent sous jsdom.
allowSlowShell();

export const MISSION_ID = "11111111-1111-4111-8111-111111111111";

/** Tous les droits à `value` ; `satisfies` garde la fabrique alignée sur le schéma. */
export function allRights(value: boolean): DroitsMission {
  return {
    modifier: value,
    planifier: value,
    lancer: value,
    emettre_ordre: value,
    suspendre: value,
    reprendre: value,
    annuler: value,
    supprimer: value,
    affecter: value,
    contribuer: value,
    voir_travaux: value,
    confirmer_ma_declaration: value,
  } satisfies DroitsMission;
}

export function aMission(overrides: Partial<Mission> = {}): Mission {
  return {
    id: MISSION_ID,
    reference: "MI-2026-001",
    titre: "Audit des achats",
    type: "ASSURANCE",
    statut: "EN_PLANIFICATION",
    phase: "PLANIFICATION",
    chef_mission: null,
    date_debut_prevue: "2026-03-02",
    date_fin_prevue: "2026-06-30",
    etape_courante: { numero: 4, romain: "IV" },
    ma_declaration_en_attente: false,
    processus_detail: [],
    entites_detail: [],
    risques_couverts_detail: [],
    evenement_declencheur: "",
    evenement_precision: "",
    periode_debut: null,
    periode_fin: null,
    budget_jours: null,
    objectifs: "",
    perimetre: "",
    exclusions: "",
    clients: "",
    livrables_attendus: "",
    cartographie: null,
    statut_avant_suspension: "",
    motif_suspension: "",
    motif_annulation: null,
    ordre_mission: null,
    ordre_mission_emis_le: null,
    equipe: [],
    mes_droits: allRights(true),
    created_at: "2026-01-05T08:00:00Z",
    ...overrides,
  } satisfies Mission;
}

export function aStep(overrides: Partial<Etape> = {}): Etape {
  return {
    id: "22222222-2222-4222-8222-222222222222",
    mission: MISSION_ID,
    numero: 1,
    romain: "I",
    titre: "Étape",
    phase: "PLANIFICATION",
    jalon: false,
    objectif: "",
    livrables: [],
    acteurs: "",
    statut: "A_FAIRE",
    date_debut_prevue: null,
    date_fin_prevue: null,
    date_debut_reelle: null,
    date_fin_reelle: null,
    charge_prevue_jours: null,
    charge_reelle_jours: null,
    terminee_par: null,
    validee_par: null,
    validee_le: null,
    motif_non_applicable: "",
    actions_possibles: [],
    predecesseurs_ouverts: [],
    livrables_manquants: [],
    evenements: [],
    ...overrides,
  } satisfies Etape;
}

const ROMAN = [
  "I",
  "II",
  "III",
  "IV",
  "V",
  "VI",
  "VII",
  "VIII",
  "IX",
  "X",
  "XI",
  "XII",
  "XIII",
  "XIV",
  "XV",
  "XVI",
  "XVII",
  "XVIII",
];

/** Les 18 étapes d'une mission ; les jalons sont VI, X, XIII et XVIII. */
export function allSteps(overrides: (numero: number) => Partial<Etape> = () => ({})): Etape[] {
  return ROMAN.map((romain, i) => {
    const numero = i + 1;
    return aStep({
      id: `00000000-0000-4000-8000-${String(numero).padStart(12, "0")}`,
      numero,
      romain,
      titre: `Titre de l'étape ${romain}`,
      phase: numero <= 10 ? "PLANIFICATION" : numero <= 14 ? "ACCOMPLISSEMENT" : "COMMUNICATION",
      jalon: [6, 10, 13, 18].includes(numero),
      ...overrides(numero),
    });
  });
}

export function pageOf<T>(results: T[]) {
  return { count: results.length, next: null, previous: null, results };
}

type Options = {
  me?: Partial<Me>;
  handlers?: RequestHandler[];
};

/** Rend les routes des missions (sous /missions) pour un rôle, avec les handlers MSW donnés. */
export function renderMission(path: string, role: Role, options: Options = {}) {
  if (options.handlers) server.use(...options.handlers);
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  const auth = authValueFor(role, vi.fn());
  const value = options.me ? { ...auth, me: auth.me && { ...auth.me, ...options.me } } : auth;
  const router = createMemoryRouter([{ path: "/missions", children: missionRoutes }], {
    initialEntries: [path],
  });
  const utils = render(
    <QueryClientProvider client={client}>
      <AuthContext.Provider value={value}>
        <RouterProvider router={router} />
      </AuthContext.Provider>
    </QueryClientProvider>,
  );
  return { ...utils, router, client };
}

/** Handlers usuels : détail de mission et ses 18 étapes. */
export function missionHandlers(mission: Mission, steps: Etape[] = allSteps()): RequestHandler[] {
  return [
    http.get(`${API_URL}/api/v1/missions/${mission.id}/`, () => HttpResponse.json(mission)),
    http.get(`${API_URL}/api/v1/mission-steps/`, () => HttpResponse.json(steps)),
  ];
}
