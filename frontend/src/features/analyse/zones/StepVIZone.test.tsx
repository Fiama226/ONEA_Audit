import { screen } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";
import {
  allSteps,
  aMission,
  missionHandlers,
  MISSION_ID,
  renderMission,
} from "@/features/missions/testUtils";
import { API_URL } from "@/test/msw";
import { aFramework, analyseRights } from "../testUtils";
import type { ReferentielAudit } from "../types";

const AUTEUR = {
  id: 7,
  username: "audite1",
  nom_complet: "Awa Ouédraogo",
  role: "AUDITE",
  direction_code: "DEX",
  fonction: "Chef de service",
} as const;

const SOUMIS = aFramework({
  statut: "SOUMIS",
  statut_v: "TERMINEE",
  statut_vi: "TERMINEE",
  nb_lignes: 2,
  nb_forces: 1,
  nb_faiblesses: 1,
  avis: [
    {
      id: "33333333-3333-4333-8333-333333333333",
      auteur: AUTEUR,
      avis: "ACCORD",
      commentaire: "",
      donne_le: "2026-03-20T09:00:00Z",
    },
  ],
});

function render(framework: ReferentielAudit) {
  return renderMission(`/missions/${MISSION_ID}/etapes/6`, "RAI", {
    handlers: [
      ...missionHandlers(aMission(), allSteps()),
      http.get(`${API_URL}/api/v1/audit-frameworks/${MISSION_ID}/`, () =>
        HttpResponse.json(framework),
      ),
    ],
  });
}

describe("StepVIZone", () => {
  it("shows the status from the server, the reminder, the opinions and the link", async () => {
    render(SOUMIS);
    expect(await screen.findByText("Soumis au RAI")).toBeInTheDocument();
    expect(screen.getByText("Awa Ouédraogo")).toBeInTheDocument();
    expect(screen.getByText("Accord")).toBeInTheDocument();
    expect(
      screen.getByText(
        "Terminer l'étape VI soumet le référentiel au Responsable de l'Audit Interne pour validation.",
      ),
    ).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Ouvrir le référentiel d'audit" })).toHaveAttribute(
      "href",
      `/missions/${MISSION_ID}/referentiel-audit`,
    );
  });

  it("shows a verified validation with the shortened hash", async () => {
    render({
      ...SOUMIS,
      statut: "VALIDE",
      validation: {
        id: "55555555-5555-4555-8555-555555555555",
        type_document: "VALIDATION_REFERENTIEL",
        signataire: { id: 1, nom_complet: "Moussa Sawadogo" },
        confirme_le: "2026-03-21T10:00:00Z",
        empreinte: "3f2a000000000000000000000000000000000000000000000000000000009c1b",
      },
      validation_verifiee: true,
    });
    expect(
      await screen.findByText(
        "Validé le 21/03/2026 par Moussa Sawadogo — empreinte 3f2a…9c1b — vérifiée",
      ),
    ).toBeInTheDocument();
  });

  it("alerts when the fingerprint is not verified", async () => {
    render({
      ...SOUMIS,
      mes_droits: analyseRights({ voir_travaux: true, voir_referentiel: true }),
      statut: "VALIDE",
      validation: {
        id: "55555555-5555-4555-8555-555555555555",
        type_document: "VALIDATION_REFERENTIEL",
        signataire: { id: 1, nom_complet: "Moussa Sawadogo" },
        confirme_le: "2026-03-21T10:00:00Z",
        empreinte: "3f2a000000000000000000000000000000000000000000000000000000009c1b",
      },
      validation_verifiee: false,
    });
    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("Empreinte non vérifiée");
  });
});
