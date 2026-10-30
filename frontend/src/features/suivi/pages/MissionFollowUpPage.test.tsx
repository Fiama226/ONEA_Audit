import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";
import { axe } from "vitest-axe";
import { API_URL, server } from "@/test/msw";
import { renderRoutes } from "@/test/shell";
import {
  aSuiviAction,
  MISSION_ID,
  missionACloturerFixture,
  pageOf,
  recommandationSuivieFixture,
} from "../testUtils";
import type { ActionSuivie, MissionACloturer } from "../types";
import { MissionFollowUpPage } from "./MissionFollowUpPage";

const BASE = `${API_URL}/api/v1/follow-up`;

function setup(
  role: "RAI" | "AUDITEUR",
  actions: ActionSuivie[],
  toClose: MissionACloturer[] = [],
) {
  const closes: unknown[] = [];
  server.use(
    http.get(`${BASE}/actions/`, () => HttpResponse.json(pageOf(actions))),
    http.get(`${BASE}/recommendations/`, () =>
      HttpResponse.json(pageOf([recommandationSuivieFixture])),
    ),
    http.get(`${BASE}/missions/`, () => HttpResponse.json(pageOf(toClose))),
    http.post(`${BASE}/missions/${MISSION_ID}/close/`, async ({ request }) => {
      closes.push(await request.json());
      return HttpResponse.json(missionACloturerFixture);
    }),
  );
  const utils = renderRoutes(
    [{ path: "/missions/:id/suivi-recommandations", element: <MissionFollowUpPage /> }],
    role,
    { path: `/missions/${MISSION_ID}/suivi-recommandations` },
  );
  return { closes, ...utils };
}

describe("MissionFollowUpPage", () => {
  it("groupe les actions par recommandation avec le statut dérivé", async () => {
    setup("AUDITEUR", [aSuiviAction()]);
    const article = await screen.findByRole("article", { name: "Fiabiliser les inventaires" });
    expect(within(article).getByText("Formaliser le rapprochement mensuel")).toBeInTheDocument();
    expect(within(article).getAllByText("À lancer").length).toBeGreaterThan(0);
    expect(screen.queryByRole("button", { name: "Clôturer la mission" })).not.toBeInTheDocument();
  });

  it("désactive la clôture et l'explique tant que des actions restent ouvertes", async () => {
    setup("RAI", [
      aSuiviAction({ statut: "EN_COURS" }),
      aSuiviAction({ id: "x", statut: "CLOTUREE" }),
    ]);
    const button = await screen.findByRole("button", { name: "Clôturer la mission" });
    await screen.findByText("1 action(s) restent ouvertes.");
    expect(button).toBeDisabled();
    expect(button).toHaveAccessibleDescription("1 action(s) restent ouvertes.");
  });

  it("clôture la mission après confirmation explicite (case non pré-cochée)", async () => {
    const user = userEvent.setup();
    const { closes } = setup(
      "RAI",
      [aSuiviAction({ statut: "CLOTUREE" })],
      [missionACloturerFixture],
    );
    const button = await screen.findByRole("button", { name: "Clôturer la mission" });
    await waitFor(() => expect(button).toBeEnabled());
    await user.click(button);
    const dialog = await screen.findByRole("alertdialog");
    const confirm = within(dialog).getByRole("button", { name: "Clôturer la mission" });
    expect(within(dialog).getByRole("checkbox")).not.toBeChecked();
    expect(confirm).toBeDisabled();
    await user.click(within(dialog).getByRole("checkbox"));
    await user.click(confirm);
    await waitFor(() => expect(closes).toEqual([{}]));
  });

  it("signale l'erreur de chargement au lieu d'un suivi vide", async () => {
    server.use(
      http.get(`${BASE}/actions/`, () => HttpResponse.json({}, { status: 500 })),
      http.get(`${BASE}/recommendations/`, () => HttpResponse.json({}, { status: 500 })),
    );
    renderRoutes(
      [{ path: "/missions/:id/suivi-recommandations", element: <MissionFollowUpPage /> }],
      "RAI",
      { path: `/missions/${MISSION_ID}/suivi-recommandations` },
    );
    expect(
      await screen.findByText("Le suivi de la mission n'a pas pu être chargé."),
    ).toBeInTheDocument();
    expect(screen.queryByText("Aucune recommandation à suivre pour cette mission.")).toBeNull();
  });

  it("n'a aucune violation axe, dialogue de clôture ouvert compris", async () => {
    const user = userEvent.setup();
    const { container } = setup(
      "RAI",
      [aSuiviAction({ statut: "CLOTUREE" })],
      [missionACloturerFixture],
    );
    const button = await screen.findByRole("button", { name: "Clôturer la mission" });
    await waitFor(() => expect(button).toBeEnabled());
    const rules = { rules: { "color-contrast": { enabled: false } } };
    expect((await axe(container, rules)).violations).toEqual([]);
    await user.click(button);
    await screen.findByRole("alertdialog");
    expect((await axe(document.body, rules)).violations).toEqual([]);
  });
});
