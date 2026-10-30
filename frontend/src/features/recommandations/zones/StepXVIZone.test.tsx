import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";
import { axe } from "vitest-axe";
import { StepActions } from "@/features/missions/components/StepActions";
import { aMission, aStep, allRights } from "@/features/missions/testUtils";
import { API_URL, server } from "@/test/msw";
import {
  ACCEPTATION_ID,
  aLigne,
  anAcceptance,
  anEngagement,
  aSummary,
  planHandlers,
} from "../planTestUtils";
import { ACTION_ID, anAction, MISSION_ID, renderPlan, RECOMMANDATION_ID } from "../testUtils";
import { StepXVIZone } from "./StepXVIZone";

const NO_CONTRAST = { rules: { "color-contrast": { enabled: false } } };
const open = aStep({ numero: 16, romain: "XVI", statut: "EN_COURS" });

function setup(
  options: Parameters<typeof planHandlers>[0] = {},
  role: "AUDITEUR" | "AUDITE" | "RAI" = "AUDITEUR",
  step = open,
) {
  server.use(...planHandlers(options));
  const mission = aMission({ mes_droits: { ...allRights(false), contribuer: role !== "AUDITE" } });
  return renderPlan(
    <>
      <StepXVIZone mission={mission} step={step} />
      <StepActions step={step} />
    </>,
    role,
  );
}

async function fillAction(user: ReturnType<typeof userEvent.setup>, due: string) {
  await user.click(await screen.findByRole("button", { name: "Ajouter une action" }));
  const dialog = await screen.findByRole("alertdialog");
  await user.type(
    within(dialog).getByLabelText("Mesure corrective"),
    "Mettre en place un rapprochement mensuel",
  );
  await user.click(await within(dialog).findByLabelText(/Fanta Sawadogo/));
  await user.type(within(dialog).getByLabelText("Échéance"), due);
  await user.type(within(dialog).getByLabelText("Indicateur de suivi"), "Rapprochements signés");
  await user.type(within(dialog).getByLabelText("Moyens nécessaires"), "1 agent, 2 j/mois");
  return dialog;
}

describe("StepXVIZone", () => {
  it("envoie la création d'une action avec les champs saisis", async () => {
    const user = userEvent.setup();
    let body: unknown;
    server.use(
      http.post(`${API_URL}/api/v1/corrective-actions/`, async ({ request }) => {
        body = await request.json();
        return HttpResponse.json(anAction(), { status: 201 });
      }),
    );
    setup();
    const dialog = await fillAction(user, "2099-12-31");
    await user.click(within(dialog).getByRole("button", { name: "Enregistrer" }));
    await screen.findByRole("article");
    expect(body).toEqual({
      recommandation: RECOMMANDATION_ID,
      libelle: "Mettre en place un rapprochement mensuel",
      responsable: 12,
      echeance: "2099-12-31",
      indicateur: "Rapprochements signés",
      moyens: "1 agent, 2 j/mois",
    });
  });

  it("bloque une échéance passée côté client puis affiche le refus du serveur sous le champ", async () => {
    const user = userEvent.setup();
    let posts = 0;
    server.use(
      http.post(`${API_URL}/api/v1/corrective-actions/`, () => {
        posts += 1;
        return HttpResponse.json(
          { detail: "Données invalides.", errors: { echeance: ["Échéance hors fenêtre."] } },
          { status: 422 },
        );
      }),
    );
    setup();
    const dialog = await fillAction(user, "2020-01-01");
    await user.click(within(dialog).getByRole("button", { name: "Enregistrer" }));
    expect(
      await within(dialog).findByText("L'échéance ne peut pas être antérieure à aujourd'hui."),
    ).toBeInTheDocument();
    expect(posts).toBe(0);

    const due = within(dialog).getByLabelText("Échéance");
    await user.clear(due);
    await user.type(due, "2099-12-31");
    await user.click(within(dialog).getByRole("button", { name: "Enregistrer" }));
    const message = await within(dialog).findByText("Échéance hors fenêtre.");
    expect(due).toHaveAttribute("aria-invalid", "true");
    expect(due.getAttribute("aria-describedby")).toContain(message.id);
    expect(due).toHaveFocus();
  });

  it("masque « Ajouter une action » quand le risque est accepté", async () => {
    setup(
      {
        summary: aSummary({
          recommandations: [
            aLigne({
              statut_derive: "RISQUE_ACCEPTE",
              acceptation: {
                id: ACCEPTATION_ID,
                auteur: 12,
                justification: "Coût disproportionné.",
              },
            }),
          ],
        }),
        acceptances: [anAcceptance()],
      },
      "RAI",
    );
    expect(
      await screen.findByText(
        "Risque accepté le 29/10/2026 par Fanta Sawadogo : Coût disproportionné.",
      ),
    ).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Ajouter une action" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Accepter le risque" })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Retirer l'acceptation" })).toBeInTheDocument();
  });

  it("n'offre aucune écriture à un audité d'une autre entité et signale l'engagement à renouveler", async () => {
    setup({ summary: aSummary({ recommandations: [] }), etat: "A_RENOUVELER" }, "AUDITE");
    expect(
      await screen.findByText("Aucune recommandation de constat validé pour le moment."),
    ).toBeInTheDocument();
    expect(await screen.findByText("À renouveler")).toBeInTheDocument();
    expect(screen.getByText(/modifié depuis votre dernière confirmation/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Ajouter une action" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Accepter le risque" })).not.toBeInTheDocument();
  });

  it("n'écrit jamais une confirmation pré-cochée : l'acceptation du risque exige la case", async () => {
    const user = userEvent.setup();
    let body: unknown;
    server.use(
      http.post(`${API_URL}/api/v1/risk-acceptances/`, async ({ request }) => {
        body = await request.json();
        return HttpResponse.json(anAcceptance(), { status: 201 });
      }),
    );
    setup({}, "AUDITE");
    await user.click(await screen.findByRole("button", { name: "Accepter le risque" }));
    const dialog = await screen.findByRole("alertdialog");
    const box = within(dialog).getByRole("checkbox");
    expect(box).not.toBeChecked();
    await user.type(within(dialog).getByLabelText("Justification de l'acceptation"), "Coût.");
    await user.click(within(dialog).getByRole("button", { name: "Confirmer l'acceptation" }));
    expect(await within(dialog).findByText("Cochez la case pour confirmer.")).toBeInTheDocument();
    expect(body).toBeUndefined();
    await user.click(box);
    await user.click(within(dialog).getByRole("button", { name: "Confirmer l'acceptation" }));
    expect(await within(dialog).findByText(/Je soussignée Fanta Sawadogo/)).toBeInTheDocument();
    expect(body).toEqual({
      recommandation: RECOMMANDATION_ID,
      justification: "Coût.",
      confirme: true,
    });
  });

  it("confirme l'engagement avec le texte du serveur, case non pré-cochée", async () => {
    const user = userEvent.setup();
    let body: unknown;
    server.use(
      http.post(`${API_URL}/api/v1/action-plan-commitments/`, async ({ request }) => {
        body = await request.json();
        return HttpResponse.json(anEngagement(), { status: 201 });
      }),
    );
    setup({ summary: aSummary({ recommandations: [] }) }, "AUDITE");
    await user.click(await screen.findByRole("button", { name: "Confirmer mon engagement" }));
    const dialog = await screen.findByRole("alertdialog");
    expect(within(dialog).getByText(/Je m'engage à réaliser les actions/)).toBeInTheDocument();
    const box = within(dialog).getByRole("checkbox");
    expect(box).not.toBeChecked();
    const submit = within(dialog).getByRole("button", { name: "Confirmer mon engagement" });
    expect(submit).toBeDisabled();
    await user.click(box);
    await user.click(submit);
    expect(await within(dialog).findByRole("status")).toHaveTextContent("Confirmé le");
    expect(body).toEqual({ mission: MISSION_ID, confirme: true });
  });

  it("modifie une action et supprime après confirmation", async () => {
    const user = userEvent.setup();
    let deleted = false;
    server.use(
      http.delete(`${API_URL}/api/v1/corrective-actions/${ACTION_ID}/`, () => {
        deleted = true;
        return new HttpResponse(null, { status: 204 });
      }),
    );
    setup(
      {
        summary: aSummary({
          recommandations: [aLigne({ nb_actions: 1, statut_derive: "A_LANCER" })],
        }),
        actions: [anAction({ actions_possibles: ["MODIFIER", "SUPPRIMER"] })],
      },
      "AUDITEUR",
    );
    expect(await screen.findByText("Rapprochements signés")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Supprimer A-01" }));
    const dialog = await screen.findByRole("alertdialog");
    await user.click(within(dialog).getByRole("checkbox"));
    await user.click(within(dialog).getByRole("button", { name: "Supprimer" }));
    await screen.findByRole("article");
    expect(deleted).toBe(true);
  });

  it("n'affiche aucune écriture quand l'étape XVI est close", async () => {
    setup(
      {
        summary: aSummary({ recommandations: [aLigne({ nb_actions: 1 })] }),
        actions: [anAction({ actions_possibles: [] })],
      },
      "AUDITEUR",
      aStep({ numero: 16, romain: "XVI", statut: "VALIDEE" }),
    );
    expect(await screen.findByText(/lecture seule/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Ajouter une action" })).not.toBeInTheDocument();
  });

  it("affiche l'erreur de chargement au lieu d'un plan vide", async () => {
    setup();
    server.use(
      http.get(`${API_URL}/api/v1/action-plans/summary/`, () =>
        HttpResponse.json({ detail: "x" }, { status: 500 }),
      ),
    );
    expect(await screen.findByRole("alert")).toHaveTextContent("Impossible de charger le plan");
    expect(
      screen.queryByText("Aucune recommandation de constat validé pour le moment."),
    ).not.toBeInTheDocument();
  });

  it("affiche les livrables manquants refusés à « Terminer l'étape »", async () => {
    const user = userEvent.setup();
    const step = aStep({
      numero: 16,
      romain: "XVI",
      statut: "EN_COURS",
      actions_possibles: ["TERMINER"],
    });
    server.use(
      http.post(`${API_URL}/api/v1/mission-steps/${step.id}/complete/`, () =>
        HttpResponse.json(
          { detail: "Livrables manquants.", errors: { livrables: ["Plan d'actions"] } },
          { status: 422 },
        ),
      ),
    );
    setup({}, "AUDITEUR", step);
    await user.click(await screen.findByRole("button", { name: "Terminer l'étape" }));
    expect(await screen.findByText("Plan d'actions", { selector: "li" })).toBeInTheDocument();
  });

  it("n'a aucune violation axe, dialogue ouvert compris", async () => {
    const user = userEvent.setup();
    const { container } = setup({ summary: aSummary({ responsables: [] }) }, "AUDITEUR");
    await user.click(await screen.findByRole("button", { name: "Ajouter une action" }));
    await screen.findByRole("alertdialog");
    expect((await axe(container, NO_CONTRAST)).violations).toEqual([]);
    expect((await axe(document.body, NO_CONTRAST)).violations).toEqual([]);
  });
});
