import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { axe } from "vitest-axe";
import { describe, expect, it } from "vitest";
import { fr } from "@/i18n/fr";
import { API_URL, server } from "@/test/msw";
import { aMission, allRights, MISSION_ID, missionHandlers, renderMission } from "../testUtils";

const m = fr.missionPilotage;
const TEXT =
  "Je soussigné(e) Awa Ouedraogo, affecté(e) à la mission, déclare n'avoir aucun conflit.";
const HASH = "3f2a" + "0".repeat(56) + "9c1b";

function setup() {
  const bodies: unknown[] = [];
  const mission = aMission({
    mes_droits: { ...allRights(false), confirmer_ma_declaration: true },
  });
  server.use(
    http.get(`${API_URL}/api/v1/independence-declarations/`, () =>
      HttpResponse.json({
        count: 1,
        next: null,
        previous: null,
        results: [
          { id: "d1", affectation: "a1", mission: MISSION_ID, statut: "EN_ATTENTE", texte: TEXT },
        ],
      }),
    ),
    http.post(`${API_URL}/api/v1/independence-declarations/d1/confirm/`, async ({ request }) => {
      const body = (await request.json()) as { conflit: boolean };
      bodies.push(body);
      return HttpResponse.json({
        id: "d1",
        mission: MISSION_ID,
        statut: body.conflit ? "CONFLIT_DECLARE" : "CONFIRMEE",
        confirmation: { confirme_le: "2026-03-05T09:30:00Z", empreinte: HASH },
      });
    }),
  );
  renderMission(`/missions/${MISSION_ID}/equipe`, "AUDITEUR", {
    handlers: missionHandlers(mission),
  });
  return bodies;
}

async function open() {
  await userEvent.click(await screen.findByRole("button", { name: m.confirmMyDeclaration }));
  expect(await screen.findByText(TEXT)).toBeInTheDocument();
}

describe("DeclarationDialog", () => {
  it("shows the server text and confirms with the exact payload and receipt", async () => {
    const bodies = setup();
    await open();
    const results = await axe(document.body, { rules: { "color-contrast": { enabled: false } } });
    expect(results.violations).toEqual([]);
    const submit = screen.getByRole("button", { name: m.declarationSubmit });
    expect(screen.getByRole("radio", { name: m.declarationConfirm })).not.toBeChecked();
    expect(screen.getByRole("radio", { name: m.declarationConflict })).not.toBeChecked();
    expect(submit).toBeDisabled();
    await userEvent.click(screen.getByRole("radio", { name: m.declarationConfirm }));
    await userEvent.click(submit);
    expect(
      await screen.findByText("Déclaration confirmée le 05/03/2026 à 09:30. Empreinte : 3f2a…9c1b"),
    ).toBeInTheDocument();
    expect(bodies).toEqual([{ confirme: true, conflit: false, description_conflit: "" }]);
  });

  it("blocks a declared situation without description", async () => {
    const bodies = setup();
    await open();
    await userEvent.click(screen.getByRole("radio", { name: m.declarationConflict }));
    await userEvent.click(screen.getByRole("button", { name: m.declarationSubmit }));
    expect(await screen.findByRole("alert")).toHaveTextContent(m.declarationDescriptionRequired);
    expect(bodies).toEqual([]);

    await userEvent.type(screen.getByLabelText(m.declarationDescription), "Lien familial.");
    await userEvent.click(screen.getByRole("button", { name: m.declarationSubmit }));
    await waitFor(() =>
      expect(bodies).toEqual([
        { confirme: true, conflit: true, description_conflit: "Lien familial." },
      ]),
    );
  });
});
