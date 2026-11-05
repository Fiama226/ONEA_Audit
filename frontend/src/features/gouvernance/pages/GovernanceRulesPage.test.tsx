import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";
import { axe } from "vitest-axe";
import type { Role } from "@/auth/types";
import { API_URL, server } from "@/test/msw";
import { renderRoutes } from "@/test/shell";
import { weakens } from "../strength";
import { aRule, allRules } from "../testUtils";
import { GovernanceRulesPage } from "./GovernanceRulesPage";

const URL = `${API_URL}/api/v1/governance-rules/`;

function renderPage(role: Role = "ADMIN") {
  return renderRoutes([{ path: "*", element: <GovernanceRulesPage /> }], role);
}

describe("GovernanceRulesPage", () => {
  it("shows every rule with its current value, read-only for the DG", async () => {
    server.use(http.get(URL, () => HttpResponse.json(allRules())));
    const { container } = renderPage("DG");
    expect(
      await screen.findByRole("heading", { name: /Approbation du programme annuel/ }),
    ).toBeInTheDocument();
    expect(screen.getByText("Direction générale puis Conseil")).toBeInTheDocument();
    expect(screen.getByText(/Lecture seule : seul l'administrateur/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Modifier/ })).not.toBeInTheDocument();
    expect(screen.getAllByText("Issue des normes")).toHaveLength(2);
    expect(
      (await axe(container, { rules: { "color-contrast": { enabled: false } } })).violations,
    ).toEqual([]);
  });

  it("warns permanently while a norm-derived rule is relaxed", async () => {
    server.use(
      http.get(URL, () =>
        HttpResponse.json(
          allRules({
            objectivity_check: {
              valeur: { mode: "WARN" },
              assouplie: true,
              motif: "Effectif réduit",
            } as never,
          }),
        ),
      ),
    );
    renderPage("RAI");
    const warning = await screen.findByRole("region", { name: "Règles assouplies" });
    expect(
      within(warning).getByText(
        /La règle « Contrôle d'objectivité », issue des normes, est assouplie/,
      ),
    ).toBeInTheDocument();
    expect(within(warning).getByText(/Effectif réduit/)).toBeInTheDocument();
    expect(screen.getByText("Avertir (affectation possible)")).toBeInTheDocument();
    expect(screen.getByText("Valeur de référence : Bloquer l'affectation")).toBeInTheDocument();
  });

  it("asks the admin for a reason before weakening a control", async () => {
    let body: unknown = null;
    server.use(
      http.get(URL, () => HttpResponse.json(allRules())),
      http.patch(`${URL}step_order/`, async ({ request }) => {
        body = await request.json();
        return HttpResponse.json(
          aRule("step_order", { valeur: { mode: "FREE" }, assouplie: true }),
        );
      }),
    );
    renderPage("ADMIN");
    await screen.findAllByText("Valeur de référence, jamais modifiée");
    await userEvent.click(screen.getByRole("button", { name: /Modifier : Ordre des étapes/ }));
    const dialog = await screen.findByRole("dialog");
    await userEvent.selectOptions(
      within(dialog).getByRole("combobox", { name: "Enchaînement des étapes" }),
      "FREE",
    );
    expect(within(dialog).getByText(/Ce changement assouplit un contrôle/)).toBeInTheDocument();
    await userEvent.click(within(dialog).getByRole("button", { name: "Enregistrer" }));
    expect(body).toBeNull();
    await userEvent.type(within(dialog).getByLabelText("Motif du changement"), "Mission pilote");
    await userEvent.click(within(dialog).getByRole("button", { name: "Enregistrer" }));
    await screen.findAllByText("Valeur de référence, jamais modifiée");
    expect(body).toEqual({ valeur: { mode: "FREE" }, motif: "Mission pilote" });
  });

  it("shows the server refusal in the dialog", async () => {
    server.use(
      http.get(URL, () => HttpResponse.json(allRules())),
      http.patch(`${URL}objectivity_check/`, () =>
        HttpResponse.json(
          {
            detail: "Données invalides.",
            errors: { cooling_off_months: ["La valeur doit être comprise entre 0 et 60."] },
          },
          { status: 400 },
        ),
      ),
    );
    renderPage("ADMIN");
    await screen.findAllByText("Valeur de référence, jamais modifiée");
    await userEvent.click(
      screen.getByRole("button", { name: /Modifier : Contrôle d'objectivité/ }),
    );
    const dialog = await screen.findByRole("dialog");
    const months = within(dialog).getByRole("spinbutton", { name: "Durée de refroidissement" });
    await userEvent.clear(months);
    await userEvent.type(months, "99");
    await userEvent.click(within(dialog).getByRole("button", { name: "Enregistrer" }));
    expect(
      await within(dialog).findByText("La valeur doit être comprise entre 0 et 60."),
    ).toBeInTheDocument();
  });
});

describe("weakens", () => {
  it("mirrors the server strength order", () => {
    expect(
      weakens("objectivity_check", { cooling_off_months: 12 }, { cooling_off_months: 6 }),
    ).toBe(true);
    expect(weakens("auditee_response", { waiver_by: "RAI" }, { waiver_by: "DG" })).toBe(false);
    expect(weakens("risk_acceptance_escalation", { high: "DG" }, { high: "RAI" })).toBe(true);
    expect(
      weakens("search_fallback", { scope: "MISSIONS" }, { scope: "MISSIONS_AND_FINDINGS" }),
    ).toBe(false);
  });
});
