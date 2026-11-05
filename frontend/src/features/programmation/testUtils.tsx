import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render } from "@testing-library/react";
import { http, HttpResponse, type RequestHandler } from "msw";
import { createMemoryRouter, RouterProvider } from "react-router-dom";
import { vi } from "vitest";
import type { Role } from "@/auth/types";
import { AuthContext } from "@/auth/useAuth";
import { API_URL, server } from "@/test/msw";
import { authValueFor } from "@/test/shell";
import { programmationRoutes } from "./routes";
import type { AuditPlan, AuditPlanLine, AuditPlanSummary } from "./types";

/** Rend les routes du programme annuel (sous /programme-annuel) avec un rôle et des handlers MSW. */
export function renderPlan(path: string, role: Role, opts: { handlers?: RequestHandler[] } = {}) {
  if (opts.handlers) server.use(...opts.handlers);
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  const router = createMemoryRouter(
    [{ path: "/programme-annuel", children: programmationRoutes }],
    {
      initialEntries: [path],
    },
  );
  const utils = render(
    <QueryClientProvider client={client}>
      <AuthContext.Provider value={authValueFor(role, vi.fn())}>
        <RouterProvider router={router} />
      </AuthContext.Provider>
    </QueryClientProvider>,
  );
  return { ...utils, router, client };
}

export const page = <T,>(results: T[]) => ({
  count: results.length,
  next: null,
  previous: null,
  results,
});

export const PLAN_ID = "5b1c7c0e-3f0a-4a53-9a8e-0d6a7a1d2c01";
export const LINE_ID = "8d4f2b6a-1c3e-4f57-b9a0-2e5c6d7f8a02";

/** Valeurs recopiées de `backend/tests/programmation/test_api_contrat.py`. */
export function aPlan(overrides: Partial<AuditPlan> = {}): AuditPlan {
  return {
    id: PLAN_ID,
    annee: 2026,
    libelle: "Programme annuel 2026",
    commentaire: "",
    statut: "BROUILLON",
    valide_le: null,
    valide_par: null,
    nb_lignes: 1,
    charge_totale_jours: "20.0",
    approbation: {
      approbateur: "DG_AND_BOARD",
      requise: true,
      approuve: false,
      manquantes: ["DG", "BOARD"],
      approbations: [],
    },
    created_at: "2026-01-05T08:00:00Z",
    updated_at: "2026-01-05T08:00:00Z",
    ...overrides,
  } satisfies AuditPlan;
}

export function aLine(overrides: Partial<AuditPlanLine> = {}): AuditPlanLine {
  return {
    id: LINE_ID,
    programme: PLAN_ID,
    programme_annee: 2026,
    programme_statut: "BROUILLON",
    numero: 1,
    titre: "Audit des achats",
    type: "ASSURANCE",
    processus: "c1a2b3d4-0000-4000-8000-000000000001",
    processus_code: "FEP",
    processus_libelle: "Approvisionnement",
    processus_supprime: false,
    objet_auditable: "c1a2b3d4-0000-4000-8000-000000000002",
    objet_auditable_libelle: "Marchés",
    objet_auditable_supprime: false,
    entites_detail: [
      {
        id: "c1a2b3d4-0000-4000-8000-000000000003",
        code: "DAF",
        libelle: "Direction administrative",
        supprime: false,
      },
    ],
    debut_prevu: "2026-05-04",
    fin_prevue: "2026-06-30",
    trimestre: 2,
    charge_prevue_jours: "20.0",
    justification: "Risque élevé",
    created_at: "2026-01-05T08:00:00Z",
    updated_at: "2026-01-05T08:00:00Z",
    ...overrides,
  } satisfies AuditPlanLine;
}

export function aSummary(overrides: Partial<AuditPlanSummary> = {}): AuditPlanSummary {
  return {
    nb_lignes: 1,
    charge_totale_jours: "20.0",
    par_type: { ASSURANCE: 1, CONSEIL: 0 },
    par_trimestre: { 1: 0, 2: 1, 3: 0, 4: 0 },
    ...overrides,
  } satisfies AuditPlanSummary;
}

/** Handler MSW d'une liste paginée en une page. */
export const listHandler = (resource: string, results: unknown[]) =>
  http.get(`${API_URL}/api/v1/${resource}/`, () => HttpResponse.json(page(results)));
