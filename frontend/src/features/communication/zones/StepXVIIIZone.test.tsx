import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";
import { axe } from "vitest-axe";
import { aDisponible } from "@/features/documents/testUtils";
import { aMission, aStep } from "@/features/missions/testUtils";
import { fr } from "@/i18n/fr";
import { API_URL, server } from "@/test/msw";
import { renderRoutes } from "@/test/shell";
import { aRapport, pageOf, RAPPORT_ID } from "../testUtils";
import type { Destinataire, Rapport } from "../types";
import { StepXVIIIZone } from "./StepXVIIIZone";

const t = fr.rapportFinal;
const NO_CONTRAST = { rules: { "color-contrast": { enabled: false } } };
const finale = (statut: "PRETE" | "EN_COURS", statut_pdf: "PRET" | "EN_COURS") => ({
  id: "ffffffff-0000-4000-8000-ffffffffffff",
  numero: 1,
  statut,
  statut_pdf,
});

function aDestinataire(overrides: Partial<Destinataire> = {}): Destinataire {
  return {
    id: "dddddddd-0000-4000-8000-dddddddddddd",
    rapport: RAPPORT_ID,
    utilisateur: null,
    utilisateur_detail: null,
    nom_externe: "Cabinet Externe",
    qualite: "Commissaire",
    categorie: "AUTRE",
    notifie_le: "2026-10-29T09:00:00Z",
    premiere_consultation_le: "2026-10-29T10:00:00Z",
    accuse_reception_le: null,
    remis_hors_plateforme_le: null,
    ...overrides,
  } as Destinataire;
}

function renderZone(rapport: Rapport, recipients: Destinataire[] = [aDestinataire()]) {
  server.use(
    http.get(`${API_URL}/api/v1/reports/`, () => HttpResponse.json(pageOf([rapport]))),
    http.get(`${API_URL}/api/v1/report-recipients/`, () => HttpResponse.json(pageOf(recipients))),
    http.get(`${API_URL}/api/v1/users/`, () => HttpResponse.json(pageOf([]))),
    http.get(`${API_URL}/api/v1/documents/available/`, () =>
      HttpResponse.json([
        aDisponible({
          type_document: "RAPPORT_FINAL",
          libelle: "Rapport d'audit",
          objet_id: RAPPORT_ID,
        }),
      ]),
    ),
  );
  return renderRoutes(
    [
      {
        path: "/",
        element: <StepXVIIIZone mission={aMission()} step={aStep({ numero: 18 })} />,
      },
    ],
    "RAI",
  );
}

describe("StepXVIIIZone", () => {
  it("désactive « Diffuser » avec la raison tant que le rapport final n'est pas généré", async () => {
    renderZone(
      aRapport({
        statut: "VALIDE",
        mode_signature: "CONFIRMATION",
        actions_possibles: ["DIFFUSER"],
      }),
    );
    const button = await screen.findByRole("button", { name: t.distribute });
    expect(button).toBeDisabled();
    expect(screen.getByText("Le rapport final n'est pas encore généré")).toBeInTheDocument();
    expect(button).toHaveAccessibleDescription("Le rapport final n'est pas encore généré");
    expect(screen.getByText("Confirmation horodatée")).toBeInTheDocument();
  });

  it("explique que le PDF n'est pas prêt", async () => {
    renderZone(
      aRapport({
        statut: "VALIDE",
        actions_possibles: ["DIFFUSER"],
        version_finale: finale("PRETE", "EN_COURS"),
      }),
    );
    expect(await screen.findByText(t.pdfNotReady)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: t.distribute })).toBeDisabled();
  });

  it("diffuse le rapport prêt après confirmation", async () => {
    let body: unknown;
    const user = userEvent.setup();
    renderZone(
      aRapport({
        statut: "VALIDE",
        actions_possibles: ["DIFFUSER"],
        version_finale: finale("PRETE", "PRET"),
      }),
    );
    server.use(
      http.post(`${API_URL}/api/v1/reports/${RAPPORT_ID}/distribute/`, async ({ request }) => {
        body = await request.json();
        return HttpResponse.json(aRapport({ statut: "DIFFUSE" }));
      }),
    );
    const button = await screen.findByRole("button", { name: t.distribute });
    await waitFor(() => expect(button).toBeEnabled());
    await user.type(screen.getByRole("textbox", { name: t.distributeMessage }), "Bonne lecture");
    await user.click(button);
    await user.click(screen.getByRole("checkbox", { name: fr.missions.confirmCheckbox }));
    await user.click(screen.getByRole("button", { name: t.distributeConfirm }));
    await waitFor(() => expect(body).toEqual({ message: "Bonne lecture" }));
  });

  it("affiche le suivi de diffusion et l'émission d'un rapport corrigé", async () => {
    let body: unknown;
    const user = userEvent.setup();
    const { container } = renderZone(
      aRapport({
        statut: "DIFFUSE",
        actions_possibles: ["CORRIGER"],
        version_finale: finale("PRETE", "PRET"),
      }),
    );
    server.use(
      http.post(`${API_URL}/api/v1/reports/${RAPPORT_ID}/correct/`, async ({ request }) => {
        body = await request.json();
        return HttpResponse.json(aRapport({ numero_version: 2 }), { status: 201 });
      }),
    );
    const table = await screen.findByRole("table", { name: t.trackingCaption });
    expect(table).toHaveTextContent("Cabinet Externe");
    expect(table).toHaveTextContent("29/10/2026 10:00");
    expect(screen.queryByRole("button", { name: t.distribute })).not.toBeInTheDocument();
    expect((await axe(container, NO_CONTRAST)).violations).toEqual([]);

    await user.click(screen.getByRole("button", { name: t.correct }));
    expect((await axe(screen.getByRole("alertdialog"), NO_CONTRAST)).violations).toEqual([]);
    await user.type(
      screen.getByRole("textbox", { name: fr.missions.motifLabel }),
      "Chiffre erroné",
    );
    await user.click(screen.getByRole("button", { name: t.correctConfirm }));
    await waitFor(() => expect(body).toEqual({ motif: "Chiffre erroné" }));
  });

  it("n'affiche pas une erreur de liste de diffusion comme une liste vide", async () => {
    renderZone(aRapport({ statut: "DIFFUSE", actions_possibles: [] }));
    server.use(
      http.get(`${API_URL}/api/v1/report-recipients/`, () =>
        HttpResponse.json({}, { status: 500 }),
      ),
    );
    await screen.findByRole("heading", { name: fr.communication.zoneXVIIITitle });
    // La liste en erreur (rechargement) ne doit pas se lire « aucun destinataire ».
    await waitFor(() => expect(screen.queryByText(t.recipientsEmpty)).not.toBeInTheDocument());
  });
});
