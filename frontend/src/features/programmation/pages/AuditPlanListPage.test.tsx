import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";
import { axe } from "vitest-axe";
import { API_URL, server } from "@/test/msw";
import { aPlan, listHandler, PLAN_ID, renderPlan } from "../testUtils";

const path = "/programme-annuel";
const plansUrl = `${API_URL}/api/v1/audit-plans/`;
const empty = () => server.use(listHandler("audit-plans", []));

describe("AuditPlanListPage", () => {
  it("lists plans with status, load and validator", async () => {
    server.use(
      listHandler("audit-plans", [
        aPlan({
          statut: "VALIDE",
          valide_le: "2026-01-20T09:00:00Z",
          valide_par: { id: 2, nom_complet: "Awa Ouedraogo" } as never,
        }),
      ]),
    );
    renderPlan(path, "AUDITEUR");
    const link = await screen.findByRole("link", { name: "2026" });
    expect(link).toHaveAttribute("href", `/programme-annuel/${PLAN_ID}`);
    expect(screen.getByText("Validé")).toBeInTheDocument();
    expect(screen.getByText("Awa Ouedraogo")).toBeInTheDocument();
    expect(screen.getByText("20/01/2026")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Créer un programme" })).not.toBeInTheDocument();
  });

  it("asks for the descending year ordering", async () => {
    let ordering: string | null = null;
    server.use(
      http.get(plansUrl, ({ request }) => {
        ordering = new URL(request.url).searchParams.get("ordering");
        return HttpResponse.json({ count: 0, next: null, previous: null, results: [] });
      }),
    );
    renderPlan(path, "RAI");
    await screen.findByText("Aucun programme annuel n'a encore été créé.");
    expect(ordering).toBe("-annee");
  });

  it("shows the empty state with a create action for the RAI", async () => {
    empty();
    renderPlan(path, "RAI");
    expect(
      await screen.findByText("Aucun programme annuel n'a encore été créé."),
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Créer un programme" })).toBeInTheDocument();
  });

  it("shows an explanation without action for other roles", async () => {
    empty();
    renderPlan(path, "AUDITEUR");
    expect(
      await screen.findByText(
        "Aucun programme annuel n'a encore été établi par le Responsable de l'audit interne.",
      ),
    ).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Créer un programme" })).not.toBeInTheDocument();
  });

  it("proposes the next year when the current one already has a plan", async () => {
    const year = new Date().getFullYear();
    server.use(listHandler("audit-plans", [aPlan({ annee: year })]));
    const user = userEvent.setup();
    renderPlan(path, "RAI");
    await user.click(await screen.findByRole("button", { name: "Créer un programme" }));
    const dialog = await screen.findByRole("dialog");
    expect(within(dialog).getByLabelText("Année")).toHaveValue(String(year + 1));
    expect(within(dialog).getByLabelText("Libellé")).toHaveValue(
      `Programme annuel d'audit interne ${year + 1}`,
    );
  });

  it("maps the 422 on annee to the year field", async () => {
    empty();
    let body: unknown;
    server.use(
      http.post(plansUrl, async ({ request }) => {
        body = await request.json();
        return HttpResponse.json(
          {
            detail: "Données invalides.",
            errors: { annee: ["Un programme annuel existe déjà pour l'année 2026."] },
          },
          { status: 422 },
        );
      }),
    );
    const user = userEvent.setup();
    renderPlan(path, "RAI");
    await user.click(await screen.findByRole("button", { name: "Créer un programme" }));
    const dialog = await screen.findByRole("dialog");
    const year = String(new Date().getFullYear());
    expect(within(dialog).getByLabelText("Année")).toHaveValue(year);
    await user.click(within(dialog).getByRole("button", { name: "Créer" }));
    expect(
      await within(dialog).findByText("Un programme annuel existe déjà pour l'année 2026."),
    ).toBeInTheDocument();
    expect(body).toMatchObject({ annee: Number(year) });
    expect(within(dialog).getByLabelText("Année")).toHaveAttribute("aria-invalid", "true");
  });

  it("shows an error state", async () => {
    server.use(http.get(plansUrl, () => HttpResponse.json({}, { status: 500 })));
    renderPlan(path, "RAI");
    expect(await screen.findByRole("alert")).toHaveTextContent("Impossible de charger");
  });

  it("has no axe violations, create dialog included", async () => {
    server.use(listHandler("audit-plans", [aPlan()]));
    const user = userEvent.setup();
    const { container } = renderPlan(path, "RAI");
    await screen.findByRole("link", { name: "2026" });
    const rules = { "color-contrast": { enabled: false } };
    expect((await axe(container, { rules })).violations).toEqual([]);
    await user.click(screen.getByRole("button", { name: "Créer un programme" }));
    const dialog = await screen.findByRole("dialog");
    expect((await axe(dialog, { rules })).violations).toEqual([]);
  });
});
