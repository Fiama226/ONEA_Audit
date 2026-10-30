import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";
import { axe } from "vitest-axe";
import type { Affectation, UtilisateurResume } from "@/features/missions/types";
import { aStep } from "@/features/missions/testUtils";
import { API_URL } from "@/test/msw";
import { aMission, aProgramme, aTest, baseHandlers, renderWithClient, TEST_ID } from "../testUtils";
import { StepIXZone } from "./StepIXZone";

const NO_CONTRAST = { rules: { "color-contrast": { enabled: false } } };
const step = aStep({ numero: 9, statut: "EN_COURS" });

function user(id: number): UtilisateurResume {
  return {
    id,
    username: `user${id}`,
    nom_complet: `Auditeur ${String(id).padStart(3, "0")}`,
    role: "AUDITEUR",
    direction_code: "DAI",
    fonction: "Auditeur",
  };
}

function member(u: UtilisateurResume): Affectation {
  return {
    id: `00000000-0000-4000-8000-${String(u.id).padStart(12, "0")}`,
    mission: aMission().id,
    utilisateur: u.id,
    utilisateur_detail: u,
    role_mission: "AUDITEUR",
    declaration: null,
  };
}

describe("StepIXZone", () => {
  it("shows the over-budget warning from the server summary", async () => {
    renderWithClient(<StepIXZone mission={aMission()} step={step} />, baseHandlers());
    expect(
      await screen.findByText("Les charges prévues dépassent le budget de la mission de 4,5 j."),
    ).toBeInTheDocument();
    expect(screen.getByText("Total : 44,5 j · Budget : 40 j")).toBeInTheDocument();
    expect(screen.getByRole("table", { name: "Charge prévue par auditeur" })).toBeInTheDocument();
  });

  it("offers all 201 team members spread over two pages and saves the resources", async () => {
    let body: unknown;
    const users = Array.from({ length: 201 }, (_, i) => user(i + 1));
    const u = userEvent.setup();
    renderWithClient(<StepIXZone mission={aMission({ equipe: users.map(member) })} step={step} />, [
      http.get(`${API_URL}/api/v1/users/`, ({ request }) => {
        const pageNumber = Number(new URL(request.url).searchParams.get("page") ?? "1");
        return HttpResponse.json({
          count: 201,
          next: pageNumber === 1 ? `${API_URL}/api/v1/users/?page=2` : null,
          previous: null,
          results: pageNumber === 1 ? users.slice(0, 200) : users.slice(200),
        });
      }),
      http.patch(`${API_URL}/api/v1/planned-tests/${TEST_ID}/`, async ({ request }) => {
        body = await request.json();
        return HttpResponse.json(aTest());
      }),
      ...baseHandlers(),
    ]);
    await u.click(
      await screen.findByRole("button", { name: "Planifier les ressources du test T-01" }),
    );
    const dialog = await screen.findByRole("dialog");
    await waitFor(() => expect(within(dialog).getAllByRole("radio")).toHaveLength(201), {
      timeout: 20000,
    });
    await u.click(within(dialog).getByLabelText(/Auditeur 201/));
    await u.type(within(dialog).getByLabelText("Charge prévue (jours)"), "12,5");
    await u.type(within(dialog).getByLabelText("Début prévu"), "2026-03-02");
    await u.type(within(dialog).getByLabelText("Fin prévue"), "2026-03-20");
    await u.click(within(dialog).getByRole("button", { name: "Enregistrer les ressources" }));
    await waitFor(() =>
      expect(body).toEqual({
        auditeur: 201,
        charge_prevue_jours: "12.5",
        date_debut_prevue: "2026-03-02",
        date_fin_prevue: "2026-03-20",
      }),
    );
  }, 60000);

  it("excludes users who are not on the mission team", async () => {
    const u = userEvent.setup();
    renderWithClient(<StepIXZone mission={aMission({ equipe: [member(user(1))] })} step={step} />, [
      http.get(`${API_URL}/api/v1/users/`, () =>
        HttpResponse.json({ count: 2, next: null, previous: null, results: [user(1), user(2)] }),
      ),
      ...baseHandlers(),
    ]);
    await u.click(
      await screen.findByRole("button", { name: "Planifier les ressources du test T-01" }),
    );
    const dialog = await screen.findByRole("dialog");
    expect(await within(dialog).findByLabelText(/Auditeur 001/)).toBeInTheDocument();
    expect(within(dialog).queryByLabelText(/Auditeur 002/)).not.toBeInTheDocument();
  });

  it("is read-only without the MODIFIER_RESSOURCES right", async () => {
    renderWithClient(
      <StepIXZone mission={aMission()} step={step} />,
      baseHandlers({ programs: [aProgramme({ actions_possibles: ["MODIFIER_CONTENU"] })] }),
    );
    expect(await screen.findByRole("cell", { name: "T-01" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Planifier/ })).not.toBeInTheDocument();
  });

  it("does not render a load error as an empty table", async () => {
    renderWithClient(<StepIXZone mission={aMission()} step={step} />, [
      http.get(`${API_URL}/api/v1/planned-tests/`, () => HttpResponse.json({}, { status: 500 })),
      ...baseHandlers(),
    ]);
    expect(
      await screen.findByText(/Impossible de charger le programme de travail/),
    ).toBeInTheDocument();
    expect(screen.queryByText(/Aucun test n'est prévu/)).not.toBeInTheDocument();
  });

  it("has no axe violation, dialog open included", async () => {
    const u = userEvent.setup();
    const { container } = renderWithClient(
      <StepIXZone mission={aMission({ equipe: [member(user(1))] })} step={step} />,
      [
        http.get(`${API_URL}/api/v1/users/`, () =>
          HttpResponse.json({ count: 1, next: null, previous: null, results: [user(1)] }),
        ),
        ...baseHandlers(),
      ],
    );
    await u.click(
      await screen.findByRole("button", { name: "Planifier les ressources du test T-01" }),
    );
    const dialog = await screen.findByRole("dialog");
    await within(dialog).findByLabelText(/Auditeur 001/);
    expect((await axe(container, NO_CONTRAST)).violations).toEqual([]);
    expect((await axe(document.body, NO_CONTRAST)).violations).toEqual([]);
  });
});
