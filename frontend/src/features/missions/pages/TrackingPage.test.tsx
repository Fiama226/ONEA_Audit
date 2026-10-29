import { screen, within } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";
import { axe } from "vitest-axe";
import type { components } from "@/api/schema";
import { API_URL } from "@/test/msw";
import { aMission, missionHandlers, MISSION_ID, renderMission } from "../testUtils";

type Fiche = components["schemas"]["FicheSuivi"];
type Ligne = components["schemas"]["LigneSuivi"];

const RAI_USER = {
  id: 900,
  username: "rai.contrat",
  nom_complet: "Awa Traore",
  role: "RAI",
  direction_code: "DAI",
  fonction: "Auditeur interne",
} satisfies components["schemas"]["UtilisateurResume"];

function ligne(numero: number, romain: string, overrides: Partial<Ligne>): Ligne {
  return {
    numero,
    romain,
    titre: `Titre ${romain}`,
    phase: "PLANIFICATION",
    jalon: false,
    statut: "TERMINEE",
    debut_prevu: "2026-03-02",
    fin_prevue: "2026-03-10",
    debut_reel: "2026-03-02",
    fin_reelle: "2026-03-13",
    ecart_jours: 0,
    charge_prevue: "2.0",
    charge_reelle: "3.5",
    ...overrides,
  } satisfies Ligne;
}

// Valeurs d'écart de `test_api_contrat_fiche_suivi` (T5) : positif = retard, négatif = avance.
const FICHE = {
  mission: { id: MISSION_ID, reference: "DAI/2026/M01", titre: "Audit des achats" },
  budget_jours: "40.0",
  total_prevu: "38.0",
  total_reel: "12.5",
  lignes: [
    ligne(3, "III", { ecart_jours: -2, fin_reelle: "2026-03-08" }),
    ligne(4, "IV", { ecart_jours: 3 }),
    ligne(5, "V", { ecart_jours: 0 }),
    ligne(6, "VI", {
      statut: "A_FAIRE",
      ecart_jours: null,
      debut_prevu: null,
      fin_prevue: null,
      debut_reel: null,
      fin_reelle: null,
      charge_prevue: null,
      charge_reelle: null,
    }),
  ],
  evenements: [
    {
      type: "TERMINEE",
      par: RAI_USER,
      le: "2026-03-13T10:00:00Z",
      motif: "",
      statut_avant: "EN_COURS",
      statut_apres: "TERMINEE",
      etape_romain: "IV",
    },
  ],
} satisfies Fiche;

function setup(fiche: Fiche = FICHE) {
  return renderMission(`/missions/${MISSION_ID}/suivi`, "RAI", {
    handlers: [
      ...missionHandlers(aMission()),
      http.get(`${API_URL}/api/v1/missions/${MISSION_ID}/tracking/`, () =>
        HttpResponse.json(fiche),
      ),
    ],
  });
}

describe("TrackingPage", () => {
  it("shows the budget line", async () => {
    setup();
    expect(
      await screen.findByText("Budget : 40 j · Prévu : 38 j · Réalisé : 12,5 j"),
    ).toBeInTheDocument();
  });

  it("shows « 3 j de retard », « 2 j d'avance », « À l'heure » and « — » per step", async () => {
    setup();
    const table = await screen.findByRole("table", { name: "Suivi des étapes par phase" });
    const row = (romain: string) =>
      within(table).getByRole("row", { name: new RegExp(`^${romain} ·`) });
    expect(within(row("IV")).getByText("3 j de retard")).toBeInTheDocument();
    expect(within(row("III")).getByText("2 j d'avance")).toBeInTheDocument();
    expect(within(row("V")).getByText("À l'heure")).toBeInTheDocument();
    expect(within(row("VI")).getAllByText("—").length).toBeGreaterThan(0);
  });

  it("groups the steps by phase with a labelled group row", async () => {
    setup();
    const table = await screen.findByRole("table", { name: "Suivi des étapes par phase" });
    expect(within(table).getAllByRole("rowgroup").length).toBeGreaterThanOrEqual(3);
    expect(within(table).getByText(/Planification\s+Étapes I–X/)).toBeInTheDocument();
    expect(within(table).getByText(/Accomplissement/)).toBeInTheDocument();
    expect(within(table).getByText(/Communication/)).toBeInTheDocument();
  });

  it("formats dates and charges", async () => {
    setup();
    const table = await screen.findByRole("table", { name: "Suivi des étapes par phase" });
    const row = within(table).getByRole("row", { name: /^IV ·/ });
    expect(within(row).getAllByText("02/03/2026").length).toBe(2);
    expect(within(row).getByText("10/03/2026")).toBeInTheDocument();
    expect(within(row).getByText("2")).toBeInTheDocument();
    expect(within(row).getByText("3,5")).toBeInTheDocument();
  });

  it("lists the chronological journal and a print header with the mission reference", async () => {
    setup();
    expect(await screen.findByText(/Fiche de suivi — DAI\/2026\/M01/)).toBeInTheDocument();
    const journal = screen.getByRole("region", { name: "Journal chronologique" });
    expect(journal).toHaveTextContent("13/03/2026 10:00");
    expect(journal).toHaveTextContent("Awa Traore");
    expect(journal).toHaveTextContent("Étape IV");
    expect(journal).toHaveTextContent("Étape terminée");
  });

  it("has no axe violation", async () => {
    const { container } = setup();
    await screen.findByText("3 j de retard");
    const results = await axe(container, { rules: { "color-contrast": { enabled: false } } });
    expect(results.violations).toEqual([]);
  });
});
