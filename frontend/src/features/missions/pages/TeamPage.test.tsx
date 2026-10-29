import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";
import { fr } from "@/i18n/fr";
import { API_URL, server } from "@/test/msw";
import { aMission, allRights, MISSION_ID, missionHandlers } from "../testUtils";
import { renderMission } from "../testUtils";
import type { Affectation, UtilisateurResume } from "../types";

const m = fr.missionPilotage;

const user = (id: number, nom: string, role: UtilisateurResume["role"]): UtilisateurResume => ({
  id,
  username: `u${id}`,
  nom_complet: nom,
  role,
  direction_code: "DAF",
  fonction: "Agent",
});

function member(
  id: number,
  nom: string,
  role: Affectation["role_mission"],
  declaration: Affectation["declaration"],
): Affectation {
  return {
    id: `aff-${id}`,
    mission: MISSION_ID,
    utilisateur: id,
    utilisateur_detail: user(id, nom, role === "AUDITE" ? "AUDITE" : "AUDITEUR"),
    role_mission: role,
    declaration,
  };
}

const TEAM = [
  member(10, "Chef Kone", "CHEF_MISSION", {
    id: "d10",
    statut: "CONFIRMEE",
    levee: false,
    confirmee_le: "2026-03-05T09:30:00Z",
  }),
  member(11, "Aude Auditeur", "AUDITEUR", {
    id: "d11",
    statut: "EN_ATTENTE",
    levee: false,
    confirmee_le: null,
  }),
  member(12, "Sita Situation", "AUDITEUR", {
    id: "d12",
    statut: "CONFLIT_DECLARE",
    levee: false,
    confirmee_le: null,
  }),
  member(13, "Arlette Arbitree", "AUDITEUR", {
    id: "d13",
    statut: "CONFLIT_DECLARE",
    levee: true,
    confirmee_le: null,
  }),
];

function serveUsers(total: number) {
  server.use(
    http.get(`${API_URL}/api/v1/users/`, ({ request }) => {
      const page = Number(new URL(request.url).searchParams.get("page") ?? "1");
      const all = Array.from({ length: total }, (_, i) =>
        user(100 + i, `Personne ${i + 1}`, "AUDITEUR"),
      );
      const results = all.slice((page - 1) * 200, page * 200);
      return HttpResponse.json({
        count: total,
        next: page * 200 < total ? "http://next" : null,
        previous: null,
        results,
      });
    }),
  );
}

function setup(rights: Partial<ReturnType<typeof allRights>>, role: "RAI" | "AUDITE" = "RAI") {
  const mission = aMission({
    equipe: TEAM,
    mes_droits: { ...allRights(false), voir_travaux: true, ...rights },
  });
  return renderMission(`/missions/${MISSION_ID}/equipe`, role, {
    handlers: missionHandlers(mission),
  });
}

describe("TeamPage", () => {
  it("shows the four declaration states in text", async () => {
    setup({});
    const table = await screen.findByRole("table");
    const rows = within(table).getAllByRole("row");
    expect(rows[1]).toHaveTextContent("Confirmée le 05/03/2026");
    expect(rows[2]).toHaveTextContent(m.declPending);
    expect(rows[3]).toHaveTextContent(m.declSituation);
    expect(rows[4]).toHaveTextContent(m.declArbitrated);
    expect(screen.queryByRole("button", { name: m.assign })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: m.replaceChief })).not.toBeInTheDocument();
  });

  it("offers every one of 201 users on two MSW pages in the picker", async () => {
    serveUsers(201);
    setup({ affecter: true });
    await userEvent.click(await screen.findByRole("button", { name: m.assign }));
    expect(await screen.findByLabelText(/Personne 201/)).toBeInTheDocument();
    expect(screen.getAllByRole("checkbox")).toHaveLength(201);
  });

  it("pre-checks the default auditees when assigning audited people", async () => {
    serveUsers(0);
    server.use(
      http.get(`${API_URL}/api/v1/users/`, () =>
        HttpResponse.json({
          count: 2,
          next: null,
          previous: null,
          results: [user(50, "Audité Un", "AUDITE"), user(51, "Audité Deux", "AUDITE")],
        }),
      ),
      http.get(`${API_URL}/api/v1/missions/${MISSION_ID}/default-auditees/`, () =>
        HttpResponse.json([user(51, "Audité Deux", "AUDITE")]),
      ),
    );
    setup({ affecter: true });
    await userEvent.click(await screen.findByRole("button", { name: m.assign }));
    await userEvent.selectOptions(await screen.findByLabelText(m.assignRole), "AUDITE");
    expect(await screen.findByLabelText(/Audité Deux/)).toBeChecked();
    expect(screen.getByLabelText(/Audité Un/)).not.toBeChecked();
  });

  it("assigns the selected person with the chosen role", async () => {
    serveUsers(3);
    const bodies: unknown[] = [];
    server.use(
      http.post(`${API_URL}/api/v1/mission-assignments/`, async ({ request }) => {
        bodies.push(await request.json());
        return HttpResponse.json(TEAM[1], { status: 201 });
      }),
    );
    setup({ affecter: true });
    await userEvent.click(await screen.findByRole("button", { name: m.assign }));
    await userEvent.click(await screen.findByLabelText(/Personne 2/));
    await userEvent.click(screen.getByRole("button", { name: m.assignConfirm }));
    await screen.findByRole("table");
    expect(bodies).toEqual([{ mission: MISSION_ID, utilisateur: 101, role_mission: "AUDITEUR" }]);
  });

  it("arbitrates a declared situation with a justification", async () => {
    let body: unknown = null;
    server.use(
      http.get(`${API_URL}/api/v1/independence-declarations/`, () =>
        HttpResponse.json({
          count: 1,
          next: null,
          previous: null,
          results: [
            {
              id: "d12",
              affectation: "aff-12",
              mission: MISSION_ID,
              description_conflit: "Parent dans l'entité auditée.",
            },
          ],
        }),
      ),
      http.post(
        `${API_URL}/api/v1/independence-declarations/d12/arbitrate/`,
        async ({ request }) => {
          body = await request.json();
          return HttpResponse.json({ id: "d12", mission: MISSION_ID });
        },
      ),
    );
    setup({ affecter: true });
    await userEvent.click(
      await screen.findByRole("button", { name: `${m.arbitrate} : Sita Situation` }),
    );
    expect(await screen.findByText(/Parent dans l'entité auditée\./)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: m.arbitrateConfirm }));
    expect(await screen.findByRole("alert")).toHaveTextContent(m.arbitrateRequired);
    await userEvent.type(
      screen.getByLabelText(m.arbitrateJustification),
      "Aucun lien avec la mission.",
    );
    await userEvent.click(screen.getByRole("button", { name: m.arbitrateConfirm }));
    await screen.findByRole("table");
    expect(body).toEqual({ justification: "Aucun lien avec la mission." });
  });
});
