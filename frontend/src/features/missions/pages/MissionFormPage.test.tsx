import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse, type RequestHandler } from "msw";
import { axe } from "vitest-axe";
import { describe, expect, it } from "vitest";
import { fr } from "@/i18n/fr";
import { API_URL } from "@/test/msw";
import {
  aMission,
  allRights,
  allSteps,
  MISSION_ID,
  missionHandlers,
  pageOf,
  renderMission,
} from "../testUtils";

const m = fr.missionPilotage;
const PROCESS_ID = "aaaaaaaa-0000-4000-8000-000000000001";
const ENTITY_ID = "bbbbbbbb-0000-4000-8000-000000000001";

const referentiel: RequestHandler[] = [
  http.get(`${API_URL}/api/v1/processes/`, () =>
    HttpResponse.json(
      pageOf([
        {
          id: PROCESS_ID,
          code: "ACH",
          libelle: "Passation des marchés",
          famille: "SUPPORT",
          ordre: 1,
          directions_detail: [],
        },
      ]),
    ),
  ),
  http.get(`${API_URL}/api/v1/directions/`, () =>
    HttpResponse.json(
      pageOf([
        {
          id: ENTITY_ID,
          code: "DAF",
          libelle: "Affaires financières",
          type: "DIRECTION",
          parent: null,
          parent_code: null,
        },
      ]),
    ),
  ),
];

async function fillRequired() {
  await userEvent.type(
    await screen.findByLabelText(fr.missions.fieldTitle),
    "Audit du processus de passation des marchés",
  );
  await userEvent.selectOptions(screen.getByLabelText(fr.missions.fieldType), "ASSURANCE");
  await userEvent.click(await screen.findByLabelText("ACH - Passation des marchés"));
  await userEvent.click(screen.getByLabelText("DAF - Affaires financières"));
  await userEvent.type(screen.getByLabelText(fr.missions.fieldStart), "2026-03-02");
  await userEvent.type(screen.getByLabelText(fr.missions.fieldEnd), "2026-05-29");
}

function submit() {
  return userEvent.click(screen.getByRole("button", { name: m.saveDraft }));
}

describe("MissionFormPage", () => {
  it("creates a mission with the expected payload", async () => {
    let body: Record<string, unknown> = {};
    renderMission("/missions/nouvelle", "RAI", {
      handlers: [
        ...referentiel,
        ...missionHandlers(aMission()),
        http.post(`${API_URL}/api/v1/missions/`, async ({ request }) => {
          body = (await request.json()) as Record<string, unknown>;
          return HttpResponse.json(aMission(), { status: 201 });
        }),
      ],
    });
    await fillRequired();
    await submit();
    await waitFor(() => expect(body.titre).toBeDefined());
    expect(body).toMatchObject({
      titre: "Audit du processus de passation des marchés",
      type: "ASSURANCE",
      processus: [PROCESS_ID],
      entites: [ENTITY_ID],
      date_debut_prevue: "2026-03-02",
      date_fin_prevue: "2026-05-29",
      budget_jours: null,
    });
  });

  it("refuses an end date before the start date on the client", async () => {
    let posted = false;
    renderMission("/missions/nouvelle", "RAI", {
      handlers: [
        ...referentiel,
        http.post(`${API_URL}/api/v1/missions/`, () => {
          posted = true;
          return HttpResponse.json(aMission(), { status: 201 });
        }),
      ],
    });
    await fillRequired();
    await userEvent.clear(screen.getByLabelText(fr.missions.fieldEnd));
    await userEvent.type(screen.getByLabelText(fr.missions.fieldEnd), "2026-02-01");
    await submit();
    expect(await screen.findByText(m.errDateOrder)).toBeInTheDocument();
    expect(posted).toBe(false);
  });

  it("shows the missing-map 422 as an alert with a link to the cartographies", async () => {
    const message =
      "Aucune cartographie des risques validée : validez une cartographie avant de créer une mission.";
    renderMission("/missions/nouvelle", "RAI", {
      handlers: [
        ...referentiel,
        http.post(`${API_URL}/api/v1/missions/`, () =>
          HttpResponse.json(
            { detail: "Règle métier.", errors: { cartographie: [message] } },
            { status: 422 },
          ),
        ),
      ],
    });
    await fillRequired();
    await submit();
    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent(message);
    expect(screen.getByRole("link", { name: m.mapLink })).toHaveAttribute(
      "href",
      "/referentiel/cartographies",
    );
    await waitFor(() => expect(alert).toHaveFocus());
  });

  it("puts the focus on the first field with a server error", async () => {
    renderMission("/missions/nouvelle", "RAI", {
      handlers: [
        ...referentiel,
        http.post(`${API_URL}/api/v1/missions/`, () =>
          HttpResponse.json(
            { detail: "Données invalides.", errors: { titre: ["Ce titre existe déjà."] } },
            { status: 400 },
          ),
        ),
      ],
    });
    await fillRequired();
    await submit();
    expect(await screen.findByText("Ce titre existe déjà.")).toBeInTheDocument();
    await waitFor(() => expect(screen.getByLabelText(fr.missions.fieldTitle)).toHaveFocus());
  });

  it("freezes the D17 fields once step I is closed, keeping dates editable", async () => {
    let patch: Record<string, unknown> = {};
    const mission = aMission({
      titre: "Audit figé",
      processus_detail: [{ id: PROCESS_ID, code: "ACH", libelle: "Passation des marchés" }],
      mes_droits: allRights(true),
    });
    renderMission(`/missions/${MISSION_ID}/modifier`, "RAI", {
      handlers: [
        ...referentiel,
        ...missionHandlers(
          mission,
          allSteps((n) => (n === 1 ? { statut: "TERMINEE" } : {})),
        ),
        http.patch(`${API_URL}/api/v1/missions/${MISSION_ID}/`, async ({ request }) => {
          patch = (await request.json()) as Record<string, unknown>;
          return HttpResponse.json(mission);
        }),
      ],
    });
    const title = await screen.findByLabelText(fr.missions.fieldTitle);
    expect(title).toBeDisabled();
    expect(screen.getByLabelText(fr.missions.fieldType)).toBeDisabled();
    expect(screen.getByLabelText(fr.missions.fieldObjectives)).toBeDisabled();
    expect(screen.getByLabelText(fr.missions.fieldStart)).toBeEnabled();
    expect(screen.getAllByText(m.frozenHelp).length).toBeGreaterThan(0);
    expect(title.className).not.toMatch(/(^|\s)opacity-50/);
    // cases figées : cochées, lisibles (ni désactivées ni à 50 %), modification sans effet
    const box = await screen.findByRole("checkbox", { name: "ACH - Passation des marchés" });
    expect(box).toBeChecked();
    expect(box).toBeEnabled();
    expect(box).toHaveAttribute("aria-readonly", "true");
    await userEvent.click(box);
    expect(box).toBeChecked();

    await submit();
    await waitFor(() => expect(Object.keys(patch).length).toBeGreaterThan(0));
    expect(patch).not.toHaveProperty("titre");
    expect(patch).not.toHaveProperty("processus");
    expect(patch).toHaveProperty("date_debut_prevue");
  });

  it("shows server errors on the processus group and focuses it", async () => {
    renderMission("/missions/nouvelle", "RAI", {
      handlers: [
        ...referentiel,
        http.post(`${API_URL}/api/v1/missions/`, () =>
          HttpResponse.json(
            { detail: "Données invalides.", errors: { processus: ["Processus inconnu."] } },
            { status: 400 },
          ),
        ),
      ],
    });
    await fillRequired();
    await submit();
    const error = await screen.findByText("Processus inconnu.");
    const group = screen.getByRole("group", { name: m.fieldProcesses });
    expect(group).toHaveAttribute("aria-describedby", error.id);
    await waitFor(() => expect(group).toHaveFocus());
  });

  it("keeps the fields editable while step I is open", async () => {
    renderMission(`/missions/${MISSION_ID}/modifier`, "RAI", {
      handlers: [...referentiel, ...missionHandlers(aMission({ mes_droits: allRights(true) }))],
    });
    expect(await screen.findByLabelText(fr.missions.fieldTitle)).toBeEnabled();
  });

  it("denies creation to a non-RAI", async () => {
    renderMission("/missions/nouvelle", "AUDITEUR", { handlers: referentiel });
    expect(await screen.findByText(fr.errors.forbiddenTitle)).toBeInTheDocument();
  });

  it("has no accessibility violation", async () => {
    const { container } = renderMission("/missions/nouvelle", "RAI", { handlers: referentiel });
    await screen.findByLabelText("ACH - Passation des marchés");
    const results = await axe(container, { rules: { "color-contrast": { enabled: false } } });
    expect(results.violations).toEqual([]);
  });
});
