import { configure } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { type RouteObject } from "react-router-dom";
import type { Role } from "@/auth/types";
import { API_URL, server } from "@/test/msw";
import { renderRoutes } from "@/test/shell";
import { beforeAll, vi } from "vitest";

// Pages complètes sous jsdom : marge pour les machines chargées (suite complète en parallèle).
beforeAll(() => {
  vi.setConfig({ testTimeout: 20000 });
  configure({ asyncUtilTimeout: 15000 });
});

export type MapFixture = {
  id: string;
  annee: number;
  libelle: string;
  commentaire: string;
  statut: string;
  source: string | null;
  validee_le: string | null;
  validee_par: { id: number; username: string; nom_complet: string } | null;
  nb_risques: number;
  created_at: string;
};

export const DRAFT: MapFixture = {
  id: "11111111-1111-4111-8111-111111111111",
  annee: 2026,
  libelle: "Cartographie des risques 2026",
  commentaire: "",
  statut: "BROUILLON",
  source: null,
  validee_le: null,
  validee_par: null,
  nb_risques: 2,
  created_at: "2026-01-05T08:00:00Z",
};

export const VALIDATED: MapFixture = {
  ...DRAFT,
  id: "22222222-2222-4222-8222-222222222222",
  annee: 2025,
  libelle: "Cartographie des risques 2025",
  statut: "VALIDEE",
  validee_le: "2026-02-10T09:30:00Z",
  validee_par: { id: 3, username: "rai", nom_complet: "Awa Ouedraogo" },
};

export function risk(overrides: Record<string, unknown> = {}) {
  return {
    id: "r-1",
    version: DRAFT.id,
    version_annee: 2026,
    version_statut: "BROUILLON",
    processus: "p-1",
    processus_code: "12-FEP",
    objet_auditable: null,
    objet_auditable_libelle: null,
    numero: 1,
    rang: 1,
    code: "12-FEP-R1",
    score: 15,
    niveau: "ELEVE",
    libelle: "Fraude sur les encaissements",
    description: "",
    probabilite: 3,
    impact: 5,
    vulnerabilite: "",
    reponse: "TRAITER",
    priorite: 1,
    objectif_controle: "",
    dispositif_controle: "",
    created_at: "2026-01-05T08:00:00Z",
    updated_at: "2026-01-05T08:00:00Z",
    ...overrides,
  };
}

export function page<T>(results: T[]) {
  return { count: results.length, next: null, previous: null, results };
}

export function matrixFor(version: MapFixture) {
  const cellules = [5, 4, 3, 2, 1].flatMap((p) =>
    [1, 2, 3, 4, 5].map((i) => ({
      probabilite: p,
      impact: i,
      score: p * i,
      niveau: p * i >= 15 ? "ELEVE" : p * i >= 8 ? "MOYEN" : "FAIBLE",
      nombre: p === 3 && i === 5 ? 1 : p === 2 && i === 2 ? 1 : 0,
      codes: p === 3 && i === 5 ? ["12-FEP-R1"] : p === 2 && i === 2 ? ["12-FEP-R2"] : [],
    })),
  );
  return {
    version: {
      id: version.id,
      annee: version.annee,
      libelle: version.libelle,
      statut: version.statut,
    },
    total: 2,
    par_niveau: { FAIBLE: 1, MOYEN: 0, ELEVE: 1 },
    cellules,
  };
}

export const R1 = risk();
export const R2 = risk({
  id: "r-2",
  code: "12-FEP-R2",
  numero: 2,
  rang: 2,
  score: 4,
  niveau: "FAIBLE",
  libelle: "Retard de facturation",
  probabilite: 2,
  impact: 2,
  reponse: "TOLERER",
  priorite: 3,
});

/** Serveur simulé minimal : processus, liste/détail de cartographies, matrice, risques. */
export function mockReferentiel(opts: { map?: MapFixture; risks?: unknown[] } = {}) {
  const map = opts.map ?? DRAFT;
  const risks = opts.risks ?? [R1, R2];
  const seen: string[] = [];
  server.use(
    http.get(`${API_URL}/api/v1/risk-maps/`, ({ request }) => {
      const statut = new URL(request.url).searchParams.get("statut");
      return HttpResponse.json(
        page([DRAFT, VALIDATED].filter((v) => !statut || v.statut === statut)),
      );
    }),
    http.get(`${API_URL}/api/v1/risk-maps/${DRAFT.id}/`, () => HttpResponse.json(DRAFT)),
    http.get(`${API_URL}/api/v1/risk-maps/${VALIDATED.id}/`, () => HttpResponse.json(VALIDATED)),
    http.get(`${API_URL}/api/v1/risk-maps/${map.id}/matrix/`, () =>
      HttpResponse.json(matrixFor(map)),
    ),
    http.get(`${API_URL}/api/v1/processes/`, () =>
      HttpResponse.json(
        page([
          {
            id: "p-1",
            code: "12-FEP",
            libelle: "Facturation et encaissement",
            famille: "REALISATION",
            ordre: 1,
            directions_detail: [],
          },
        ]),
      ),
    ),
    http.get(`${API_URL}/api/v1/auditable-objects/tree/`, () => HttpResponse.json([])),
    // Risques proposés par les missions (panneau du RAI sur une cartographie en brouillon).
    http.get(`${API_URL}/api/v1/mission-risks/`, () => HttpResponse.json(page([]))),
    http.get(`${API_URL}/api/v1/risks/`, ({ request }) => {
      const url = new URL(request.url);
      seen.push(url.search);
      const p = url.searchParams.get("probabilite");
      const i = url.searchParams.get("impact");
      const list = (risks as { probabilite: number; impact: number }[]).filter(
        (r) => (!p || r.probabilite === Number(p)) && (!i || r.impact === Number(i)),
      );
      return HttpResponse.json(page(list));
    }),
  );
  return seen;
}

export function renderCarto(routes: RouteObject[], role: Role, path: string) {
  return renderRoutes(routes, role, { path });
}
