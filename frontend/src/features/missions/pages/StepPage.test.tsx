import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";
import { axe } from "vitest-axe";
import { API_URL } from "@/test/msw";
import {
  allSteps,
  aMission,
  missionHandlers,
  MISSION_ID,
  pageOf,
  renderMission,
} from "../testUtils";

const NO_CONTRAST = { rules: { "color-contrast": { enabled: false } } };
const stepUrl = (n: number) => `/missions/${MISSION_ID}/etapes/${n}`;
const stepId = (n: number) => `00000000-0000-4000-8000-${String(n).padStart(12, "0")}`;

function render(
  numero: number,
  role: "RAI" | "AUDITEUR",
  steps: ReturnType<typeof allSteps>,
  extra: Parameters<typeof renderMission>[2] = {},
) {
  return renderMission(stepUrl(numero), role, {
    ...extra,
    handlers: [
      ...missionHandlers(aMission(), steps),
      ...(extra.handlers ?? []),
      // Les panneaux de l'étape II (entretiens, déclarations, réunions) chargent leurs listes :
      // sans handler, la requête non gérée rend une alerte d'erreur concurrente.
      ...["interviews", "independence-declarations", "meetings"].map((path) =>
        http.get(`${API_URL}/api/v1/${path}/`, () => HttpResponse.json(pageOf([]))),
      ),
    ],
  });
}

const VI_TERMINEE = allSteps((n) =>
  n === 6
    ? {
        statut: "TERMINEE",
        actions_possibles: ["VALIDER", "RENVOYER", "ROUVRIR"],
        titre: "Valider le programme de travail",
      }
    : {},
);

describe("StepPage", () => {
  it("shows the step header, phase, milestone mention and expected deliverables", async () => {
    render(
      6,
      "RAI",
      allSteps((n) =>
        n === 6
          ? {
              statut: "TERMINEE",
              objectif: "Valider le programme",
              livrables: ["Programme de travail"],
              livrables_manquants: ["Programme de travail signé"],
            }
          : {},
      ),
    );
    expect(
      await screen.findByRole("heading", { level: 2, name: /Étape VI — Titre de l'étape VI/ }),
    ).toBeInTheDocument();
    expect(screen.getByText(/Phase : Planification/)).toBeInTheDocument();
    expect(screen.getByText(/Jalon validé par le RAI/)).toBeInTheDocument();
    expect(screen.getByText("Programme de travail")).toBeInTheDocument();
    expect(screen.getByText("Manquant : Programme de travail signé")).toBeInTheDocument();
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent("Audit des achats");
  });

  it("mounts the lot 7 zone skeleton for step XV", async () => {
    render(15, "RAI", allSteps());
    expect(await screen.findByRole("heading", { name: "Rapport provisoire" })).toBeInTheDocument();
  });

  it("offers « Valider le jalon » to the RAI when the server allows it", async () => {
    render(6, "RAI", VI_TERMINEE);
    expect(await screen.findByRole("button", { name: "Valider le jalon" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Renvoyer" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Rouvrir l'étape" })).toBeInTheDocument();
  });

  it("shows no write button when actions_possibles is empty", async () => {
    render(
      6,
      "AUDITEUR",
      allSteps((n) => (n === 6 ? { statut: "TERMINEE", actions_possibles: [] } : {})),
    );
    await screen.findByRole("heading", { level: 2, name: /Étape VI/ });
    expect(screen.queryByRole("button", { name: "Valider le jalon" })).not.toBeInTheDocument();
    expect(screen.queryByRole("group", { name: "Actions sur l'étape" })).not.toBeInTheDocument();
  });

  it("validates the milestone after an explicit confirmation", async () => {
    const calls: string[] = [];
    const user = userEvent.setup();
    render(6, "RAI", VI_TERMINEE, {
      handlers: [
        http.post(`${API_URL}/api/v1/mission-steps/${stepId(6)}/validate/`, () => {
          calls.push("validate");
          return HttpResponse.json({ ...VI_TERMINEE[5], statut: "VALIDEE", actions_possibles: [] });
        }),
      ],
    });
    await user.click(await screen.findByRole("button", { name: "Valider le jalon" }));
    const dialog = await screen.findByRole("alertdialog");
    const confirm = within(dialog).getByRole("button", { name: "Valider le jalon" });
    expect(confirm).toBeDisabled();
    await user.click(within(dialog).getByRole("checkbox"));
    await user.click(confirm);
    await waitFor(() => expect(calls).toEqual(["validate"]));
  });

  it("lists the three missing deliverables when « Terminer l'étape » is refused (422)", async () => {
    const user = userEvent.setup();
    render(
      2,
      "AUDITEUR",
      allSteps((n) => (n === 2 ? { statut: "EN_COURS", actions_possibles: ["TERMINER"] } : {})),
      {
        handlers: [
          http.post(`${API_URL}/api/v1/mission-steps/${stepId(2)}/complete/`, () =>
            HttpResponse.json(
              {
                detail: "Étape incomplète.",
                errors: {
                  livrables: [
                    "La réunion d'ouverture n'est pas marquée comme tenue.",
                    "Aucun entretien n'est planifié.",
                    "Déclarations d'indépendance en attente : Awa Traore.",
                  ],
                },
              },
              { status: 422 },
            ),
          ),
        ],
      },
    );
    await user.click(await screen.findByRole("button", { name: "Terminer l'étape" }));
    const alert = await screen.findByRole("alert");
    expect(within(alert).getAllByRole("listitem")).toHaveLength(3);
    expect(alert).toHaveTextContent("Aucun entretien n'est planifié.");
  });

  it("does not carry a refused-completion alert over to the next step", async () => {
    const user = userEvent.setup();
    render(
      2,
      "AUDITEUR",
      allSteps((n) =>
        n === 2 || n === 3 ? { statut: "EN_COURS", actions_possibles: ["TERMINER"] } : {},
      ),
      {
        handlers: [
          http.post(`${API_URL}/api/v1/mission-steps/${stepId(2)}/complete/`, () =>
            HttpResponse.json(
              {
                detail: "Étape incomplète.",
                errors: { livrables: ["Aucun entretien n'est planifié."] },
              },
              { status: 422 },
            ),
          ),
        ],
      },
    );
    await user.click(await screen.findByRole("button", { name: "Terminer l'étape" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Aucun entretien");
    const next = screen
      .getAllByRole("link")
      .find((a) => a.getAttribute("href") === `/missions/${MISSION_ID}/etapes/3`);
    await user.click(next as HTMLElement);
    await screen.findByRole("heading", { level: 2, name: /Étape III —/ });
    expect(screen.queryByText("Aucun entretien n'est planifié.")).not.toBeInTheDocument();
  });

  it("requires a reason to reopen a step and sends it", async () => {
    const bodies: unknown[] = [];
    const user = userEvent.setup();
    render(6, "RAI", VI_TERMINEE, {
      handlers: [
        http.post(`${API_URL}/api/v1/mission-steps/${stepId(6)}/reopen/`, async ({ request }) => {
          bodies.push(await request.json());
          return HttpResponse.json({ ...VI_TERMINEE[5], statut: "EN_COURS" });
        }),
      ],
    });
    await user.click(await screen.findByRole("button", { name: "Rouvrir l'étape" }));
    const dialog = await screen.findByRole("alertdialog");
    await user.click(within(dialog).getByRole("button", { name: "Rouvrir l'étape" }));
    expect(await within(dialog).findByText("Le motif est obligatoire.")).toBeInTheDocument();
    expect(bodies).toEqual([]);
    await user.type(within(dialog).getByLabelText("Motif"), "Programme à reprendre");
    await user.click(within(dialog).getByRole("button", { name: "Rouvrir l'étape" }));
    await waitFor(() => expect(bodies).toEqual([{ motif: "Programme à reprendre" }]));
  });

  it("shows the planning form only with PLANIFIER and saves it", async () => {
    const bodies: unknown[] = [];
    const user = userEvent.setup();
    render(
      2,
      "RAI",
      allSteps((n) => (n === 2 ? { statut: "EN_COURS", actions_possibles: ["PLANIFIER"] } : {})),
      {
        handlers: [
          http.patch(`${API_URL}/api/v1/mission-steps/${stepId(2)}/`, async ({ request }) => {
            bodies.push(await request.json());
            return HttpResponse.json(allSteps()[1]);
          }),
        ],
      },
    );
    await user.type(await screen.findByLabelText("Début prévu"), "2026-03-02");
    await user.type(screen.getByLabelText("Fin prévue"), "2026-03-10");
    await user.type(screen.getByLabelText("Charge prévue (jours)"), "2,5");
    await user.click(screen.getByRole("button", { name: "Enregistrer" }));
    await waitFor(() =>
      expect(bodies).toEqual([
        {
          date_debut_prevue: "2026-03-02",
          date_fin_prevue: "2026-03-10",
          charge_prevue_jours: "2.5",
          charge_reelle_jours: null,
        },
      ]),
    );
  });

  it("hides the planning form without PLANIFIER", async () => {
    render(2, "AUDITEUR", allSteps());
    await screen.findByRole("heading", { level: 2, name: /Étape II/ });
    expect(screen.queryByLabelText("Début prévu")).not.toBeInTheDocument();
  });

  it("lists the journal events with date, author, action and reason", async () => {
    render(
      6,
      "RAI",
      allSteps((n) =>
        n === 6
          ? {
              evenements: [
                {
                  type: "RENVOYEE",
                  par: {
                    id: 900,
                    username: "rai",
                    nom_complet: "Awa Traore",
                    role: "RAI",
                    direction_code: "DAI",
                    fonction: "RAI",
                  },
                  le: "2026-03-13T10:00:00Z",
                  motif: "Programme incomplet",
                  statut_avant: "TERMINEE",
                  statut_apres: "RENVOYEE",
                },
              ],
            }
          : {},
      ),
    );
    const journal = await screen.findByRole("region", { name: "Journal de l'étape" });
    expect(within(journal).getByText("13/03/2026 10:00")).toBeInTheDocument();
    expect(within(journal).getByText("Awa Traore")).toBeInTheDocument();
    expect(within(journal).getByText("Étape renvoyée")).toBeInTheDocument();
    expect(within(journal).getByText("Programme incomplet")).toBeInTheDocument();
  });

  it.each([0, 19, 99])("shows « Étape introuvable » as an alert for step %i", async (n) => {
    render(n, "RAI", allSteps());
    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("Étape introuvable.");
  });

  it("keeps a valid heading order (h1, h2, h3) and has no axe violation with a dialog open", async () => {
    const user = userEvent.setup();
    const { container } = render(6, "RAI", VI_TERMINEE);
    await screen.findByRole("heading", { level: 2, name: /Étape VI/ });
    const levels = screen.getAllByRole("heading").map((h) => Number(h.tagName.slice(1)));
    levels.forEach((level, i) => {
      if (i > 0) expect(level - (levels[i - 1] ?? 0)).toBeLessThanOrEqual(1);
    });
    expect((await axe(container, NO_CONTRAST)).violations).toEqual([]);
    await user.click(screen.getByRole("button", { name: "Renvoyer" }));
    const dialog = await screen.findByRole("alertdialog");
    expect((await axe(dialog, NO_CONTRAST)).violations).toEqual([]);
  });
});
