import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";
import { axe } from "vitest-axe";
import { fr } from "@/i18n/fr";
import { API_URL } from "@/test/msw";
import {
  aMission,
  allRights,
  MISSION_ID,
  missionHandlers,
  pageOf,
  renderMission,
} from "../testUtils";
import type { Reunion, UtilisateurResume } from "../types";

const t = fr.missionTravaux;

const kabore: UtilisateurResume = {
  id: 5,
  username: "m.kabore",
  nom_complet: "Mamadou Kaboré",
  role: "AUDITEUR",
  direction_code: "DAI",
  fonction: "Auditeur",
};

function aMeeting(overrides: Partial<Reunion> = {}): Reunion {
  return {
    id: "33333333-3333-4333-8333-333333333333",
    mission: MISSION_ID,
    type: "OUVERTURE",
    date: "2026-03-02T09:00:00Z",
    lieu: "Salle A",
    ordre_du_jour: "Présentation de la mission",
    participants: [5],
    participants_detail: [kabore],
    participants_externes: "Mme Kaboré — Directrice — DCL",
    decisions: "",
    compte_rendu: "",
    tenue_le: null,
    etape_close: false,
    ...overrides,
  };
}

function handlers(meetings: Reunion[], mission = aMission()) {
  return [
    ...missionHandlers(mission),
    http.get(`${API_URL}/api/v1/meetings/`, () => HttpResponse.json(pageOf(meetings))),
    http.get(`${API_URL}/api/v1/users/`, () => HttpResponse.json(pageOf([kabore]))),
  ];
}

const PATH = `/missions/${MISSION_ID}/reunions`;

describe("MeetingsPage", () => {
  it("plans the opening meeting with the expected payload", async () => {
    let body: unknown;
    renderMission(PATH, "RAI", {
      handlers: [
        ...handlers([]),
        http.post(`${API_URL}/api/v1/meetings/`, async ({ request }) => {
          body = await request.json();
          return HttpResponse.json(aMeeting(), { status: 201 });
        }),
      ],
    });
    const buttons = await screen.findAllByRole("button", { name: t.planMeeting });
    expect(buttons).toHaveLength(3);
    await userEvent.click(buttons[0]!);
    const dialog = await screen.findByRole("dialog");
    fireEvent.change(within(dialog).getByLabelText(t.dateLabel), {
      target: { value: "2026-03-02T09:00" },
    });
    await userEvent.click(await within(dialog).findByLabelText(/Mamadou Kaboré/));
    await userEvent.type(
      within(dialog).getByLabelText(t.externalParticipants),
      "Mme Kaboré — Directrice — DCL",
    );
    await userEvent.click(within(dialog).getByRole("button", { name: fr.common.save }));
    await waitFor(() => expect(body).toBeDefined());
    expect(body).toEqual({
      mission: MISSION_ID,
      type: "OUVERTURE",
      date: "2026-03-02T09:00:00+00:00",
      participants: [5],
      participants_externes: "Mme Kaboré — Directrice — DCL",
    });
  });

  it("requires a date client side", async () => {
    renderMission(PATH, "RAI", { handlers: handlers([]) });
    await userEvent.click((await screen.findAllByRole("button", { name: t.planMeeting }))[0]!);
    const dialog = await screen.findByRole("dialog");
    await userEvent.click(within(dialog).getByRole("button", { name: fr.common.save }));
    expect(await within(dialog).findByText(t.dateRequired)).toBeInTheDocument();
  });

  it("shows the meeting details and status", async () => {
    renderMission(PATH, "RAI", { handlers: handlers([aMeeting()]) });
    expect(await screen.findByText("Salle A")).toBeInTheDocument();
    expect(screen.getByText(t.statusPlanned)).toBeInTheDocument();
    expect(screen.getByText(/Mamadou Kaboré/)).toBeInTheDocument();
    expect(screen.getAllByText(t.pvLater)).toHaveLength(3);
  });

  it("displays the server refusal when marking held without minutes", async () => {
    renderMission(PATH, "RAI", {
      handlers: [
        ...handlers([aMeeting()]),
        http.post(`${API_URL}/api/v1/meetings/:id/mark-held/`, () =>
          HttpResponse.json(
            {
              detail: "Saisissez le compte rendu avant de marquer la réunion comme tenue.",
              errors: {
                compte_rendu: [
                  "Saisissez le compte rendu avant de marquer la réunion comme tenue.",
                ],
              },
            },
            { status: 422 },
          ),
        ),
      ],
    });
    await userEvent.click(await screen.findByRole("button", { name: t.markHeld }));
    const dialog = await screen.findByRole("alertdialog");
    await userEvent.click(within(dialog).getByLabelText(fr.missions.confirmCheckbox));
    await userEvent.click(within(dialog).getByRole("button", { name: t.markHeld }));
    expect(await within(dialog).findByRole("alert")).toHaveTextContent(
      "Saisissez le compte rendu avant de marquer la réunion comme tenue.",
    );
  });

  it("edits a meeting with PATCH and sends emptied fields", async () => {
    let body: unknown;
    renderMission(PATH, "RAI", {
      handlers: [
        ...handlers([aMeeting()]),
        http.patch(`${API_URL}/api/v1/meetings/:id/`, async ({ request }) => {
          body = await request.json();
          return HttpResponse.json(aMeeting());
        }),
      ],
    });
    await userEvent.click(await screen.findByRole("button", { name: t.editMeeting }));
    const dialog = await screen.findByRole("dialog");
    await userEvent.clear(within(dialog).getByLabelText(t.placeLabel));
    await userEvent.click(within(dialog).getByRole("button", { name: fr.common.save }));
    await waitFor(() => expect(body).toBeDefined());
    expect(body).toMatchObject({ lieu: "", mission: MISSION_ID, type: "OUVERTURE" });
  });

  it("shows the frozen-mission refusal and the 403 message in the form", async () => {
    const frozen = "La mission MI-2026-001 est suspendue : aucune modification n'est possible.";
    renderMission(PATH, "RAI", {
      handlers: [
        ...handlers([aMeeting()]),
        http.patch(`${API_URL}/api/v1/meetings/:id/`, () =>
          HttpResponse.json({ detail: frozen, errors: {} }, { status: 422 }),
        ),
      ],
    });
    await userEvent.click(await screen.findByRole("button", { name: t.editMeeting }));
    const dialog = await screen.findByRole("dialog");
    await userEvent.click(within(dialog).getByRole("button", { name: fr.common.save }));
    expect(await within(dialog).findByRole("alert")).toHaveTextContent(frozen);
  });

  it("shows a 403 refusal in the form", async () => {
    renderMission(PATH, "RAI", {
      handlers: [
        ...handlers([aMeeting()]),
        http.patch(`${API_URL}/api/v1/meetings/:id/`, () =>
          HttpResponse.json({ detail: "Accès refusé.", errors: {} }, { status: 403 }),
        ),
      ],
    });
    await userEvent.click(await screen.findByRole("button", { name: t.editMeeting }));
    const dialog = await screen.findByRole("dialog");
    await userEvent.click(within(dialog).getByRole("button", { name: fr.common.save }));
    expect(await within(dialog).findByRole("alert")).toHaveTextContent("Accès refusé.");
  });

  it("keeps a deactivated participant visible and removable", async () => {
    let body: { participants?: number[] } = {};
    const ghost = { ...kabore, id: 7, nom_complet: "Ancien Agent" };
    renderMission(PATH, "RAI", {
      handlers: [
        ...handlers([aMeeting({ participants: [7], participants_detail: [ghost] })]),
        http.patch(`${API_URL}/api/v1/meetings/:id/`, async ({ request }) => {
          body = (await request.json()) as { participants?: number[] };
          return HttpResponse.json(aMeeting());
        }),
      ],
    });
    await userEvent.click(await screen.findByRole("button", { name: t.editMeeting }));
    const dialog = await screen.findByRole("dialog");
    const box = await within(dialog).findByLabelText("Ancien Agent (compte désactivé)");
    await userEvent.click(box);
    await userEvent.click(within(dialog).getByRole("button", { name: fr.common.save }));
    await waitFor(() => expect(body.participants).toEqual([]));
  });

  it("shows server errors on participants in the form alert", async () => {
    renderMission(PATH, "RAI", {
      handlers: [
        ...handlers([aMeeting()]),
        http.patch(`${API_URL}/api/v1/meetings/:id/`, () =>
          HttpResponse.json(
            {
              detail: "Données invalides.",
              errors: { participants: ['Clé primaire "99" invalide.'] },
            },
            { status: 400 },
          ),
        ),
      ],
    });
    await userEvent.click(await screen.findByRole("button", { name: t.editMeeting }));
    const dialog = await screen.findByRole("dialog");
    await userEvent.click(within(dialog).getByRole("button", { name: fr.common.save }));
    expect(await within(dialog).findByRole("alert")).toHaveTextContent("Clé primaire");
  });

  it("shows « Tenue le » once held", async () => {
    renderMission(PATH, "RAI", {
      handlers: handlers([aMeeting({ tenue_le: "2026-03-02T11:00:00Z" })]),
    });
    expect(await screen.findByText("Tenue le 02/03/2026")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: t.markHeld })).not.toBeInTheDocument();
  });

  it("is read-only when the step is closed", async () => {
    renderMission(PATH, "RAI", { handlers: handlers([aMeeting({ etape_close: true })]) });
    expect(await screen.findByText(t.readOnlyClosed)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: t.markHeld })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: t.editMeeting })).not.toBeInTheDocument();
  });

  it("shows no action to the auditee", async () => {
    renderMission(PATH, "AUDITE", {
      handlers: handlers([aMeeting()], aMission({ mes_droits: allRights(false) })),
    });
    expect(await screen.findByText("Salle A")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: t.planMeeting })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: t.markHeld })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: t.editMeeting })).not.toBeInTheDocument();
  });

  it("has no accessibility violation with the dialog open", async () => {
    renderMission(PATH, "RAI", { handlers: handlers([]) });
    await userEvent.click((await screen.findAllByRole("button", { name: t.planMeeting }))[0]!);
    const dialog = await screen.findByRole("dialog");
    await within(dialog).findByLabelText(/Mamadou Kaboré/);
    const results = await axe(dialog, { rules: { "color-contrast": { enabled: false } } });
    expect(results.violations).toEqual([]);
  });
});
