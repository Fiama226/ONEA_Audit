import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render } from "@testing-library/react";
import { http, HttpResponse, type RequestHandler } from "msw";
import type { ReactNode } from "react";
import { aMission, MISSION_ID } from "@/features/missions/testUtils";
import type { ObjectifAudit } from "@/features/analyse/types";
import { API_URL, server } from "@/test/msw";
import type { ProgrammeTravail, SyntheseProgramme, TestPrevu } from "./types";

export const OBJECTIVE_ID = "55555555-5555-4555-8555-555555555555";
export const PROGRAM_ID = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa";
export const TEST_ID = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb";

export { aMission, MISSION_ID };

export function page<T>(results: T[]) {
  return { count: results.length, next: null, previous: null, results };
}

export function anObjective(overrides: Partial<ObjectifAudit> = {}): ObjectifAudit {
  return {
    id: OBJECTIVE_ID,
    mission: MISSION_ID,
    ligne_marc: "33333333-3333-4333-8333-333333333333",
    code: "OA-01",
    numero: 1,
    libelle: "Vérifier les rapprochements",
    retenu: true,
    motif_non_test: "",
    justification: "",
    risque_code: "R-001",
    controle_existant: "",
    ...overrides,
  } satisfies ObjectifAudit;
}

export function aProgramme(overrides: Partial<ProgrammeTravail> = {}): ProgrammeTravail {
  return {
    id: PROGRAM_ID,
    mission: MISSION_ID,
    objectif: OBJECTIVE_ID,
    objectif_detail: { id: OBJECTIVE_ID, code: "OA-01", libelle: "Vérifier les rapprochements" },
    techniques: "Extraction du journal des achats",
    criteres_preuve: "Bons de commande signés",
    commentaire: "",
    nb_tests: 1,
    actions_possibles: ["MODIFIER_CONTENU", "MODIFIER_RESSOURCES"],
    ...overrides,
  } satisfies ProgrammeTravail;
}

export function aTest(overrides: Partial<TestPrevu> = {}): TestPrevu {
  return {
    id: TEST_ID,
    mission: MISSION_ID,
    programme: PROGRAM_ID,
    code: "T-01",
    libelle: "Examen des factures",
    objectif_test: "",
    nature: "EXAMEN_DOCUMENTAIRE",
    procedure: "Rapprocher les factures des bons de commande",
    population: "Factures 2025",
    taille_echantillon: 25,
    methode_selection: "ALEATOIRE",
    auditeur: null,
    auditeur_detail: null as unknown as TestPrevu["auditeur_detail"],
    charge_prevue_jours: null,
    date_debut_prevue: null,
    date_fin_prevue: null,
    risque_mission: null,
    risque_code: "",
    complementaire: false,
    statut: "PREVU",
    motif_abandon: "",
    fiche: null,
    actions_possibles: ["MODIFIER", "SUPPRIMER"],
    ...overrides,
  } satisfies TestPrevu;
}

/** Synthèse au format exact du test de contrat serveur `test_api_contrat_synthese`. */
export function aSummary(overrides: Partial<SyntheseProgramme> = {}): SyntheseProgramme {
  return {
    objectifs: [
      { code: "OA-01", libelle: "Vérifier les rapprochements", nb_tests: 1, charge: "30.0" },
      { code: "OA-02", libelle: "Contrôler les stocks", nb_tests: 1, charge: "14.5" },
    ],
    auditeurs: [
      {
        utilisateur: {
          id: 7,
          username: "awa.ouedraogo",
          nom_complet: "Awa Ouedraogo",
          role: "AUDITEUR",
          direction_code: "DAI",
          fonction: "Auditeur",
        },
        nb_tests: 2,
        charge: "44.5",
      },
    ],
    total_charge: "44.5",
    budget_jours: "40.0",
    depassement_budget: true,
    tests_sans_auditeur: [],
    ...overrides,
  } satisfies SyntheseProgramme;
}

export function renderWithClient(ui: ReactNode, handlers: RequestHandler[] = []) {
  server.use(...handlers);
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(<QueryClientProvider client={client}>{ui}</QueryClientProvider>);
}

export function baseHandlers({
  objectives = [anObjective()],
  programs = [aProgramme()],
  tests = [aTest()],
  summary = aSummary(),
}: {
  objectives?: ObjectifAudit[];
  programs?: ProgrammeTravail[];
  tests?: TestPrevu[];
  summary?: SyntheseProgramme;
} = {}): RequestHandler[] {
  return [
    http.get(`${API_URL}/api/v1/audit-objectives/`, () => HttpResponse.json(page(objectives))),
    http.get(`${API_URL}/api/v1/work-programs/summary/`, () => HttpResponse.json(summary)),
    http.get(`${API_URL}/api/v1/work-programs/`, () => HttpResponse.json(page(programs))),
    http.get(`${API_URL}/api/v1/planned-tests/`, () => HttpResponse.json(page(tests))),
    http.get(`${API_URL}/api/v1/mission-risks/`, () => HttpResponse.json(page([]))),
  ];
}
