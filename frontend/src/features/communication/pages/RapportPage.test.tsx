import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";
import { axe } from "vitest-axe";
import type { Role } from "@/auth/types";
import { fr } from "@/i18n/fr";
import { API_URL, server } from "@/test/msw";
import { renderRoutes } from "@/test/shell";
import { aRapport, MISSION_ID, pageOf, RAPPORT_ID } from "../testUtils";
import type { Rapport } from "../types";
import { RapportPage } from "./RapportPage";

const t = fr.rapportFinal;
const NO_CONTRAST = { rules: { "color-contrast": { enabled: false } } };

function handlers(rapport: Rapport | null) {
  return [
    http.get(`${API_URL}/api/v1/reports/`, () =>
      HttpResponse.json(pageOf(rapport ? [rapport] : [])),
    ),
    http.get(`${API_URL}/api/v1/reports/${RAPPORT_ID}/preview/`, () =>
      HttpResponse.json({
        sections: { synthese: "Synthèse assemblée" },
        constats: [{ reference: "C-01", titre: "Écart de stock", entite: "Agence A" }],
      }),
    ),
    http.get(`${API_URL}/api/v1/reports/${RAPPORT_ID}/validation-text/`, () =>
      HttpResponse.json({
        texte: "Je valide le rapport RA-2026-001.",
        mode: "CONFIRMATION",
        confirmation_requise: true,
        signature_electronique_requise: false,
      }),
    ),
  ];
}

function renderPage(rapport: Rapport | null, role: Role = "AUDITEUR") {
  server.use(...handlers(rapport));
  return renderRoutes([{ path: "/missions/:id/rapport", element: <RapportPage /> }], role, {
    path: `/missions/${MISSION_ID}/rapport`,
  });
}

describe("RapportPage — accès", () => {
  it("refuse l'accès direct à l'audité au lieu de planter", async () => {
    renderPage(aRapport(), "AUDITE");
    expect(await screen.findByText(fr.errors.forbiddenTitle)).toBeInTheDocument();
  });
});

describe("RapportPage — rédaction", () => {
  it("propose de créer le rapport lorsqu'il n'existe pas", async () => {
    let created: unknown;
    const user = userEvent.setup();
    renderPage(null);
    server.use(
      http.post(`${API_URL}/api/v1/reports/`, async ({ request }) => {
        created = await request.json();
        return HttpResponse.json(aRapport(), { status: 201 });
      }),
    );
    await user.click(await screen.findByRole("button", { name: t.createReport }));
    await waitFor(() => expect(created).toEqual({ mission: MISSION_ID }));
  });

  it("enregistre les sections explicitement, sans enregistrement automatique", async () => {
    const bodies: Record<string, unknown>[] = [];
    const user = userEvent.setup();
    renderPage(aRapport({ actions_possibles: ["MODIFIER", "SOUMETTRE"] }));
    server.use(
      http.patch(`${API_URL}/api/v1/reports/${RAPPORT_ID}/`, async ({ request }) => {
        bodies.push((await request.json()) as Record<string, unknown>);
        return HttpResponse.json(aRapport({ synthese: "Nouvelle synthèse" }));
      }),
    );
    const synthese = await screen.findByRole("textbox", { name: t.sections.synthese });
    await user.type(synthese, "Nouvelle synthèse");
    await user.click(screen.getByRole("radio", { name: "Perfectible" }));
    expect(bodies).toHaveLength(0);
    await user.click(screen.getByRole("button", { name: t.save }));
    await waitFor(() => expect(bodies).toHaveLength(1));
    expect(bodies[0]).toMatchObject({
      synthese: "Nouvelle synthèse",
      appreciation_globale: "PERFECTIBLE",
    });
    expect(await screen.findByText(t.saved)).toBeInTheDocument();
  });

  it("affiche le compteur de caractères", async () => {
    const user = userEvent.setup();
    renderPage(aRapport({ actions_possibles: ["MODIFIER"] }));
    await user.type(await screen.findByRole("textbox", { name: t.sections.conclusion }), "abc");
    expect(screen.getAllByText("3 caractères").length).toBeGreaterThan(0);
  });

  it("met le formulaire en lecture seule une fois le rapport soumis", async () => {
    renderPage(aRapport({ statut: "SOUMIS", actions_possibles: [] }));
    const synthese = await screen.findByRole("textbox", { name: t.sections.synthese });
    expect(synthese).toHaveAttribute("readonly");
    expect(screen.queryByRole("button", { name: t.save })).not.toBeInTheDocument();
    expect(screen.getByRole("radio", { name: "Perfectible" })).toBeDisabled();
  });

  it("relie l'erreur serveur au champ (aria-describedby) et place le focus", async () => {
    const user = userEvent.setup();
    renderPage(aRapport({ actions_possibles: ["MODIFIER"] }));
    server.use(
      http.patch(`${API_URL}/api/v1/reports/${RAPPORT_ID}/`, () =>
        HttpResponse.json(
          { detail: "Invalide", errors: { synthese: ["La synthèse est trop longue."] } },
          { status: 422 },
        ),
      ),
    );
    await user.click(await screen.findByRole("button", { name: t.save }));
    const synthese = await screen.findByRole("textbox", { name: t.sections.synthese });
    const message = await screen.findByText("La synthèse est trop longue.");
    await waitFor(() => expect(synthese).toHaveFocus());
    expect(synthese).toHaveAttribute("aria-invalid", "true");
    expect(synthese.getAttribute("aria-describedby")).toContain(message.id);
  });

  it("n'affiche jamais une erreur de chargement comme un rapport vide", async () => {
    server.use(
      http.get(`${API_URL}/api/v1/reports/`, () => HttpResponse.json({}, { status: 500 })),
    );
    renderRoutes([{ path: "/missions/:id/rapport", element: <RapportPage /> }], "AUDITEUR", {
      path: `/missions/${MISSION_ID}/rapport`,
    });
    expect(await screen.findByRole("alert")).toHaveTextContent(t.loadError);
    expect(screen.queryByRole("button", { name: t.createReport })).not.toBeInTheDocument();
  });

  it("affiche l'aperçu non figé sans bouton à l'impression", async () => {
    renderPage(aRapport({ actions_possibles: ["MODIFIER"] }));
    const preview = await screen.findByRole("article", { name: t.previewTitle });
    expect(await within(preview).findByText("Synthèse assemblée")).toBeInTheDocument();
    expect(within(preview).getByText(t.previewBanner)).toBeInTheDocument();
    expect(within(preview).queryAllByRole("button")).toHaveLength(0);
  });

  it("montre le motif de renvoi en alerte", async () => {
    renderPage(
      aRapport({
        statut: "RENVOYE",
        motif_renvoi: "Conclusion à reprendre",
        actions_possibles: ["MODIFIER"],
      }),
    );
    expect(await screen.findByRole("alert")).toHaveTextContent("Conclusion à reprendre");
  });
});

describe("RapportPage — soumission et validation", () => {
  it("soumet au RAI après confirmation", async () => {
    let called = false;
    const user = userEvent.setup();
    renderPage(aRapport({ actions_possibles: ["MODIFIER", "SOUMETTRE"] }));
    server.use(
      http.post(`${API_URL}/api/v1/reports/${RAPPORT_ID}/submit/`, () => {
        called = true;
        return HttpResponse.json(aRapport({ statut: "SOUMIS" }));
      }),
    );
    await user.click(await screen.findByRole("button", { name: t.submit }));
    await user.click(screen.getByRole("checkbox", { name: fr.missions.confirmCheckbox }));
    await user.click(screen.getByRole("button", { name: t.submitConfirm }));
    await waitFor(() => expect(called).toBe(true));
  });

  it("ne montre pas « Valider le rapport » au chef de mission", async () => {
    renderPage(aRapport({ statut: "SOUMIS", actions_possibles: [] }));
    expect(await screen.findByText(t.awaitingRai)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: t.validate })).not.toBeInTheDocument();
  });

  it("fait valider le RAI avec la case cochée et le texte exact du serveur", async () => {
    let body: unknown;
    const user = userEvent.setup();
    renderPage(aRapport({ statut: "SOUMIS", actions_possibles: ["VALIDER", "RENVOYER"] }), "RAI");
    server.use(
      http.post(`${API_URL}/api/v1/reports/${RAPPORT_ID}/validate/`, async ({ request }) => {
        body = await request.json();
        return HttpResponse.json(aRapport({ statut: "VALIDE" }));
      }),
    );
    expect(await screen.findByText("Confirmation horodatée")).toBeInTheDocument();
    await user.click(await screen.findByRole("button", { name: t.validate }));
    expect(screen.getByText("Je valide le rapport RA-2026-001.")).toBeInTheDocument();
    const checkbox = screen.getByRole("checkbox", { name: fr.communication.confirmCheckbox });
    expect(checkbox).not.toBeChecked();
    const dialog = screen.getByRole("alertdialog");
    const confirm = within(dialog).getByRole("button", { name: t.validate });
    expect(confirm).toBeDisabled();
    await user.click(checkbox);
    await user.click(confirm);
    await waitFor(() => expect(body).toEqual({ confirme: true }));
  });

  it("exige un motif pour renvoyer le rapport", async () => {
    let body: unknown;
    const user = userEvent.setup();
    renderPage(aRapport({ statut: "SOUMIS", actions_possibles: ["VALIDER", "RENVOYER"] }), "RAI");
    server.use(
      http.post(`${API_URL}/api/v1/reports/${RAPPORT_ID}/return/`, async ({ request }) => {
        body = await request.json();
        return HttpResponse.json(aRapport({ statut: "RENVOYE" }));
      }),
    );
    await user.click(await screen.findByRole("button", { name: t.returnAction }));
    await user.click(screen.getByRole("button", { name: t.returnConfirm }));
    expect(await screen.findByText(fr.missions.motifRequired)).toBeInTheDocument();
    expect(body).toBeUndefined();
    await user.type(screen.getByRole("textbox", { name: fr.missions.motifLabel }), "À reprendre");
    await user.click(screen.getByRole("button", { name: t.returnConfirm }));
    await waitFor(() => expect(body).toEqual({ motif: "À reprendre" }));
  });

  it("n'a aucune violation axe, dialogue de validation ouvert compris", async () => {
    const user = userEvent.setup();
    const { container } = renderPage(
      aRapport({ statut: "SOUMIS", actions_possibles: ["VALIDER", "RENVOYER"] }),
      "RAI",
    );
    await screen.findByText(t.modes.CONFIRMATION);
    await user.click(await screen.findByRole("button", { name: t.validate }));
    expect((await axe(container, NO_CONTRAST)).violations).toEqual([]);
    expect((await axe(screen.getByRole("alertdialog"), NO_CONTRAST)).violations).toEqual([]);
  });
});
