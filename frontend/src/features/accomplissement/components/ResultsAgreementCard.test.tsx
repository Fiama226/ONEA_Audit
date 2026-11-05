import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";
import { aMission, MISSION_ID } from "@/features/missions/testUtils";
import { API_URL, server } from "@/test/msw";
import { renderWithAuth } from "@/test/shell";
import { ResultsAgreementCard } from "./ResultsAgreementCard";

const ENTITE = "22222222-2222-4222-8222-222222222222";
const AGREEMENTS = `${API_URL}/api/v1/test-results-agreements/`;

function mission(responsable: boolean) {
  return aMission({
    statut: "EN_ACCOMPLISSEMENT",
    entites_detail: [{ id: ENTITE, code: "DEX", libelle: "Direction de l'exploitation" }],
    equipe: [
      {
        id: "aff-7",
        mission: MISSION_ID,
        utilisateur: 7,
        utilisateur_detail: {
          id: 7,
          username: "audite1",
          nom_complet: "Issa Kaboré",
          role: "AUDITE",
          direction_code: "DEX",
          fonction: "",
        },
        role_mission: "AUDITE",
        responsable_entite: responsable,
        declaration: null,
        alerte_objectivite: "",
      },
    ],
  });
}

describe("ResultsAgreementCard", () => {
  it("lets the entity head give a reasoned disagreement", async () => {
    let body: unknown = null;
    server.use(
      http.get(`${API_URL}/api/v1/missions/${MISSION_ID}/`, () => HttpResponse.json(mission(true))),
      http.get(AGREEMENTS, () => HttpResponse.json([])),
      http.post(AGREEMENTS, async ({ request }) => {
        body = await request.json();
        return HttpResponse.json({}, { status: 201 });
      }),
    );
    renderWithAuth(<ResultsAgreementCard missionId={MISSION_ID} />, "AUDITE", "/", {
      id: 7,
      direction_code: "DEX",
    });
    await userEvent.click(await screen.findByLabelText("Désaccord"));
    await userEvent.click(screen.getByRole("button", { name: "Enregistrer la position" }));
    expect(await screen.findByText("Motivez le désaccord.")).toBeInTheDocument();
    expect(body).toBeNull();
    await userEvent.type(
      screen.getByLabelText("Commentaire (obligatoire en cas de désaccord)"),
      "Échantillon non représentatif",
    );
    await userEvent.click(screen.getByRole("button", { name: "Enregistrer la position" }));
    await screen.findByRole("button", { name: "Enregistrer la position" });
    expect(body).toEqual({
      mission: MISSION_ID,
      entite: ENTITE,
      position: "DESACCORD",
      commentaire: "Échantillon non représentatif",
    });
  });

  it("stays hidden for an auditee who is not the entity head", async () => {
    server.use(
      http.get(`${API_URL}/api/v1/missions/${MISSION_ID}/`, () =>
        HttpResponse.json(mission(false)),
      ),
      http.get(AGREEMENTS, () => HttpResponse.json([])),
    );
    const { container } = renderWithAuth(
      <ResultsAgreementCard missionId={MISSION_ID} />,
      "AUDITE",
      "/",
      { id: 7, direction_code: "DEX" },
    );
    await new Promise((r) => setTimeout(r, 50));
    expect(container.querySelector("section")).toBeNull();
  });
});
