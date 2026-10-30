import { screen, within } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";
import { axe } from "vitest-axe";
import { API_URL, server } from "@/test/msw";
import { renderWithAuth } from "@/test/shell";
import { tableauAuditeurFixture } from "../fixtures";
import { DashboardAuditeur } from "./DashboardAuditeur";

const URL_ = `${API_URL}/api/v1/dashboards/auditor/`;
const M = "11111111-1111-4111-8111-111111111111";

const full = {
  ...tableauAuditeurFixture,
  mes_etapes_en_cours: [
    {
      mission_id: M,
      reference: "MI-2026-001",
      numero: 9,
      romain: "IX",
      libelle: "Tests",
      date_fin_prevue: "2026-10-27",
      en_retard: true,
    },
  ],
  mes_tests_a_documenter: [
    {
      test_id: "t1",
      mission_id: M,
      reference: "MI-2026-001",
      code: "T-01",
      libelle: "Rapprochement",
      sans_fiche: true,
    },
  ],
};

describe("DashboardAuditeur", () => {
  it("affiche les liens vers missions, étapes, tests et actions", async () => {
    server.use(http.get(URL_, () => HttpResponse.json(full)));
    const { container } = renderWithAuth(<DashboardAuditeur />, "AUDITEUR");
    const missions = await screen.findByRole("region", { name: "Mes missions" });
    expect(within(missions).getByRole("link", { name: "MI-2026-001" })).toHaveAttribute(
      "href",
      `/missions/${M}`,
    );
    expect(screen.getByRole("link", { name: "Étape IX — Tests" })).toHaveAttribute(
      "href",
      `/missions/${M}/etapes/9`,
    );
    expect(screen.getByText("En retard")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "T-01 — Rapprochement" })).toHaveAttribute(
      "href",
      `/missions/${M}/etapes/12`,
    );
    expect(
      screen.getByRole("link", { name: "Formaliser le rapprochement mensuel" }),
    ).toHaveAttribute("href", "/recommandations/actions/55555555-5555-4555-8555-555555555555");
    const results = await axe(container, { rules: { "color-contrast": { enabled: false } } });
    expect(results.violations).toEqual([]);
  });

  it("affiche les états vides", async () => {
    server.use(
      http.get(URL_, () =>
        HttpResponse.json({
          mes_missions: [],
          mes_etapes_en_cours: [],
          mes_tests_a_documenter: [],
          actions_a_verifier: [],
        }),
      ),
    );
    renderWithAuth(<DashboardAuditeur />, "AUDITEUR");
    expect(await screen.findByText("Aucune mission ne vous est confiée.")).toBeInTheDocument();
    expect(screen.getByText("Aucune action en attente de vérification.")).toBeInTheDocument();
  });

  it("ne rend pas une erreur comme un tableau vide", async () => {
    server.use(http.get(URL_, () => HttpResponse.json({}, { status: 500 })));
    renderWithAuth(<DashboardAuditeur />, "AUDITEUR");
    expect(await screen.findByRole("alert")).toHaveTextContent("n'a pas pu être chargé");
    expect(screen.queryByText("Aucune mission ne vous est confiée.")).not.toBeInTheDocument();
  });

  it("signale le chargement", () => {
    server.use(http.get(URL_, () => new Promise(() => {})));
    renderWithAuth(<DashboardAuditeur />, "AUDITEUR");
    expect(screen.getByRole("status")).toBeInTheDocument();
  });
});
