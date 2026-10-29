import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";
import { fr } from "@/i18n/fr";
import { API_URL, server } from "@/test/msw";
import {
  aMission,
  allRights,
  MISSION_ID,
  missionHandlers,
  pageOf,
  renderMission,
} from "../testUtils";
import type { DroitsMission } from "../types";

const m = fr.missionPilotage;
const URL = `${API_URL}/api/v1/missions/${MISSION_ID}`;

function setup(
  statut: "PLANIFIEE" | "BROUILLON" | "EN_PLANIFICATION",
  rights: Partial<DroitsMission>,
) {
  const mission = aMission({
    statut,
    mes_droits: { ...allRights(false), ...rights },
  });
  return renderMission(`/missions/${MISSION_ID}/equipe`, "RAI", {
    handlers: missionHandlers(mission),
  });
}

async function openMenu() {
  await userEvent.click(await screen.findByRole("button", { name: fr.missions.actionsMenu }));
}

describe("MissionActions", () => {
  it("offers only the granted actions (PLANIFIEE: launch yes, plan no)", async () => {
    setup("PLANIFIEE", { lancer: true, suspendre: true, annuler: true, modifier: true });
    await openMenu();
    const names = screen.getAllByRole("menuitem").map((i) => i.textContent);
    expect(names).toEqual([m.actionEdit, m.actionLaunch, m.actionSuspend, m.actionCancel]);
    expect(screen.queryByRole("menuitem", { name: m.actionPlan })).not.toBeInTheDocument();
  });

  it("launches the mission after a plain confirmation", async () => {
    let called = false;
    server.use(
      http.post(`${URL}/launch/`, () => {
        called = true;
        return HttpResponse.json(aMission());
      }),
    );
    setup("PLANIFIEE", { lancer: true });
    await openMenu();
    await userEvent.click(screen.getByRole("menuitem", { name: m.actionLaunch }));
    await userEvent.click(await screen.findByRole("button", { name: m.confirmLaunch }));
    await waitFor(() => expect(called).toBe(true));
  });

  it("lists the missing fields returned by a 422 on plan", async () => {
    server.use(
      http.post(`${URL}/plan/`, () =>
        HttpResponse.json(
          {
            detail: "Des informations obligatoires manquent.",
            errors: { objectifs: ["Les objectifs sont obligatoires."] },
          },
          { status: 422 },
        ),
      ),
    );
    setup("BROUILLON", { planifier: true });
    await openMenu();
    await userEvent.click(screen.getByRole("menuitem", { name: m.actionPlan }));
    await userEvent.click(await screen.findByRole("button", { name: m.confirmPlan }));
    expect(await screen.findByText("Les objectifs sont obligatoires.")).toBeInTheDocument();
    expect(screen.getByText("Des informations obligatoires manquent.")).toBeInTheDocument();
  });

  it("refuses an empty cancellation motif, shows the irreversibility text and the 422", async () => {
    let body: unknown = null;
    server.use(
      http.post(`${URL}/cancel/`, async ({ request }) => {
        body = await request.json();
        return HttpResponse.json(
          { detail: "La mission est déjà annulée.", errors: {} },
          { status: 422 },
        );
      }),
    );
    setup("PLANIFIEE", { annuler: true });
    await openMenu();
    await userEvent.click(screen.getByRole("menuitem", { name: m.actionCancel }));
    expect(await screen.findByText(m.cancelText)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: m.confirmCancel }));
    expect(await screen.findByRole("alert")).toHaveTextContent(fr.missions.motifRequired);
    expect(body).toBeNull();

    await userEvent.type(screen.getByLabelText(fr.missions.motifLabel), "Abandon du projet");
    await userEvent.click(screen.getByRole("button", { name: m.confirmCancel }));
    expect(await screen.findByText("La mission est déjà annulée.")).toBeInTheDocument();
    expect(body).toEqual({ motif: "Abandon du projet" });
  });

  it("deletes a draft without refetching the deleted mission", async () => {
    let detailFetches = 0;
    const mission = aMission({
      statut: "BROUILLON",
      mes_droits: { ...allRights(false), supprimer: true },
    });
    renderMission(`/missions/${MISSION_ID}/equipe`, "RAI", {
      handlers: [
        http.get(`${URL}/`, () => {
          detailFetches += 1;
          return HttpResponse.json(mission);
        }),
        http.get(`${API_URL}/api/v1/mission-steps/`, () => HttpResponse.json([])),
        http.delete(`${URL}/`, () => new HttpResponse(null, { status: 204 })),
        http.get(`${API_URL}/api/v1/missions/`, () => HttpResponse.json(pageOf([]))),
      ],
    });
    await openMenu();
    const beforeDelete = detailFetches;
    await userEvent.click(screen.getByRole("menuitem", { name: m.actionDelete }));
    await userEvent.click(await screen.findByRole("checkbox"));
    await userEvent.click(screen.getByRole("button", { name: m.confirmDelete }));
    expect(await screen.findByText(m.emptyRai)).toBeInTheDocument();
    expect(detailFetches).toBe(beforeDelete);
  });
});
