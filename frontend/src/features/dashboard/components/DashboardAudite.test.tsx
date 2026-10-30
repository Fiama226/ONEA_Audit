import { screen, within } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";
import { axe } from "vitest-axe";
import { API_URL, server } from "@/test/msw";
import { renderWithAuth } from "@/test/shell";
import { tableauAuditeFixture } from "../fixtures";
import { DashboardAudite } from "./DashboardAudite";

const URL_ = `${API_URL}/api/v1/dashboards/auditee/`;
const M = "11111111-1111-4111-8111-111111111111";
const S = "55555555-5555-4555-8555-555555555555";

const full = {
  constats_a_repondre: [
    {
      constat_id: "c1",
      mission_id: M,
      mission_reference: "MI-2026-001",
      reference: "C-01",
      titre: "Écart de caisse",
      cycle: 1,
      soumis_le: "2026-10-20T08:00:00Z",
    },
  ],
  mes_actions: [
    {
      ...tableauAuditeFixture.mes_actions[0],
      suivi_id: "tard",
      libelle: "Plus tard",
      echeance: "2026-12-01",
      en_retard: false,
      jours_retard: null,
    },
    tableauAuditeFixture.mes_actions[0],
  ],
  mes_demandes_report: [
    {
      demande_id: "d1",
      suivi_id: S,
      reference: "MI-2026-001",
      echeance_actuelle: "2026-10-27",
      nouvelle_echeance: "2026-11-30",
      statut: "EN_ATTENTE",
    },
  ],
};

describe("DashboardAudite", () => {
  it("affiche constats, actions triées par échéance et retard en texte", async () => {
    server.use(http.get(URL_, () => HttpResponse.json(full)));
    const { container } = renderWithAuth(<DashboardAudite />, "AUDITE");
    expect(await screen.findByRole("link", { name: "C-01 — Écart de caisse" })).toHaveAttribute(
      "href",
      `/missions/${M}/constats/c1`,
    );
    const actions = screen.getByRole("region", { name: "Mes actions" });
    const rows = within(actions).getAllByRole("row");
    expect(
      within(rows[1]!).getByRole("link", { name: "Formaliser le rapprochement mensuel" }),
    ).toHaveAttribute("href", `/recommandations/actions/${S}`);
    expect(within(rows[2]!).getByText("Plus tard")).toBeInTheDocument();
    expect(screen.getByText("en retard de 3 j")).toBeInTheDocument();
    expect(screen.getByText("En attente")).toBeInTheDocument();
    const results = await axe(container, { rules: { "color-contrast": { enabled: false } } });
    expect(results.violations).toEqual([]);
  });

  it("affiche l'état vide des actions", async () => {
    server.use(
      http.get(URL_, () =>
        HttpResponse.json({ constats_a_repondre: [], mes_actions: [], mes_demandes_report: [] }),
      ),
    );
    renderWithAuth(<DashboardAudite />, "AUDITE");
    expect(await screen.findByText("Aucune action ne vous est confiée.")).toBeInTheDocument();
  });

  it("ne rend pas une erreur comme un tableau vide", async () => {
    server.use(http.get(URL_, () => HttpResponse.json({}, { status: 500 })));
    renderWithAuth(<DashboardAudite />, "AUDITE");
    expect(await screen.findByRole("alert")).toBeInTheDocument();
    expect(screen.queryByText("Aucune action ne vous est confiée.")).not.toBeInTheDocument();
  });
});
