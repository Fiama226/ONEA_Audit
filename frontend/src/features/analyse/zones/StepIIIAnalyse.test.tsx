import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse, type RequestHandler } from "msw";
import { describe, expect, it } from "vitest";
import { axe } from "vitest-axe";
import {
  aMission,
  MISSION_ID,
  missionHandlers,
  pageOf,
  renderMission,
} from "@/features/missions/testUtils";
import { fr } from "@/i18n/fr";
import { API_URL } from "@/test/msw";
import { aFramework, aGrid, aQuestionnaire, analyseRights } from "../testUtils";
import type { Question } from "../types";

const t = fr.analyseIII;
const NO_CONTRAST = { rules: { "color-contrast": { enabled: false } } };
const PROCESS = { id: "88888888-8888-4888-8888-888888888888", code: "P-ACH", libelle: "Achats" };
const QUESTIONNAIRE_ID = "66666666-6666-4666-8666-666666666666";

function aQuestion(n: number, overrides: Partial<Question> = {}): Question {
  return {
    id: `q-${n}`,
    questionnaire: QUESTIONNAIRE_ID,
    theme: n <= 2 ? "Organisation" : "Systèmes",
    libelle: `Question ${n}`,
    reponse: "",
    appreciation: "",
    ordre: n,
    repondue: false,
    ...overrides,
  };
}

type Setup = {
  contribuer?: boolean;
  questionnaires?: ReturnType<typeof aQuestionnaire>[];
  questions?: Question[];
  grids?: ReturnType<typeof aGrid>[];
  extra?: RequestHandler[];
};

function open({ contribuer = true, questionnaires, questions, grids, extra = [] }: Setup = {}) {
  const mission = aMission({ processus_detail: [PROCESS] });
  const state = { questions: questions ?? [], grids: grids ?? [] };
  const bodies: Record<string, unknown> = {};
  renderMission(`/missions/${MISSION_ID}/etapes/3`, "RAI", {
    handlers: [
      ...extra,
      ...missionHandlers(mission),
      http.get(`${API_URL}/api/v1/interviews/`, () => HttpResponse.json(pageOf([]))),
      http.get(`${API_URL}/api/v1/audit-frameworks/${MISSION_ID}/`, () =>
        HttpResponse.json(
          aFramework({
            mes_droits: analyseRights({ voir_travaux: true, contribuer_iii: contribuer }),
          }),
        ),
      ),
      http.get(`${API_URL}/api/v1/analysis-questionnaires/`, ({ request }) => {
        const type = new URL(request.url).searchParams.get("type");
        return HttpResponse.json(pageOf((questionnaires ?? []).filter((q) => q.type === type)));
      }),
      http.get(`${API_URL}/api/v1/analysis-questions/`, () =>
        HttpResponse.json(pageOf(state.questions)),
      ),
      http.patch(`${API_URL}/api/v1/analysis-questions/:id/`, async ({ request, params }) => {
        const body = (await request.json()) as Partial<Question>;
        bodies.patch = body;
        state.questions = state.questions.map((q) =>
          q.id === params.id ? { ...q, ...body, repondue: Boolean(body.appreciation) } : q,
        );
        return HttpResponse.json(state.questions.find((q) => q.id === params.id));
      }),
      http.get(`${API_URL}/api/v1/process-descriptions/`, () => HttpResponse.json(pageOf([]))),
      http.get(`${API_URL}/api/v1/segregation-grids/`, () =>
        HttpResponse.json(pageOf(state.grids)),
      ),
    ],
  });
  return bodies;
}

describe("StepIIIAnalyse", () => {
  it("creates the questionnaire with mission and type only", async () => {
    let body: unknown;
    open({
      extra: [
        http.post(`${API_URL}/api/v1/analysis-questionnaires/`, async ({ request }) => {
          body = await request.json();
          return HttpResponse.json(aQuestionnaire(), { status: 201 });
        }),
      ],
    });
    await userEvent.click(await screen.findByRole("button", { name: t.createQuestionnaire }));
    await waitFor(() => expect(body).toEqual({ mission: MISSION_ID, type: "PRISE_CONNAISSANCE" }));
  });

  it("saves an answer with PATCH and updates the counter", async () => {
    const questions = Array.from({ length: 11 }, (_, i) => aQuestion(i + 1));
    const bodies = open({ questionnaires: [aQuestionnaire()], questions });
    expect(await screen.findByText("0 / 11 questions renseignées")).toBeInTheDocument();
    const select = screen.getByRole("combobox", { name: "Appréciation : Question 1" });
    await userEvent.selectOptions(select, "OUI");
    await userEvent.type(screen.getByRole("textbox", { name: "Réponse : Question 1" }), "Conforme");
    await userEvent.click(screen.getAllByRole("button", { name: t.saveQuestion })[0]!);
    expect(await screen.findByText("1 / 11 questions renseignées")).toBeInTheDocument();
    expect(bodies.patch).toEqual({ appreciation: "OUI", reponse: "Conforme" });
  });

  it("shows server errors on the answer field", async () => {
    open({
      questionnaires: [aQuestionnaire()],
      questions: [aQuestion(1)],
      extra: [
        http.patch(`${API_URL}/api/v1/analysis-questions/:id/`, () =>
          HttpResponse.json(
            { detail: "Refusé", errors: { reponse: ["Fenêtre de saisie close."] } },
            { status: 422 },
          ),
        ),
      ],
    });
    await userEvent.click(await screen.findByRole("button", { name: t.saveQuestion }));
    const field = await screen.findByRole("textbox", { name: "Réponse : Question 1" });
    expect(await screen.findByText("Fenêtre de saisie close.")).toBeInTheDocument();
    expect(field).toHaveAttribute("aria-invalid", "true");
    expect(field).toHaveAttribute("aria-describedby");
  });

  it("saves a segregation grid and displays the server cumulation alert", async () => {
    let sent: { cellules?: unknown } = {};
    const store: ReturnType<typeof aGrid>[] = [];
    open({
      grids: store,
      extra: [
        http.post(`${API_URL}/api/v1/segregation-grids/`, async ({ request }) => {
          sent = (await request.json()) as typeof sent;
          const saved = aGrid({
            taches: ["Émettre le bon de commande"],
            acteurs: ["Acheteur"],
            cellules: [{ tache: 0, acteur: 0, roles: ["EXECUTE", "AUTORISE"] }],
            analyse: {
              taches_sans_acteur: ["Payer"],
              taches_multi_executants: [],
              cumuls: [
                {
                  tache: "Émettre le bon de commande",
                  acteur: "Acheteur",
                  roles: ["EXECUTE", "AUTORISE"],
                },
              ],
            },
          });
          store.splice(0, store.length, saved);
          return HttpResponse.json(saved, { status: 201 });
        }),
      ],
    });
    await userEvent.click(await screen.findByRole("button", { name: t.gridAddTask }));
    await userEvent.click(screen.getByRole("button", { name: t.gridAddActor }));
    await userEvent.type(
      screen.getByLabelText(t.gridTaskName.replace("{n}", "1")),
      "Émettre le bon de commande",
    );
    await userEvent.type(screen.getByLabelText(t.gridActorName.replace("{n}", "1")), "Acheteur");
    await userEvent.click(
      screen.getByRole("checkbox", { name: "Émettre le bon de commande — Acheteur — Exécute" }),
    );
    await userEvent.click(
      screen.getByRole("checkbox", { name: "Émettre le bon de commande — Acheteur — Autorise" }),
    );
    await userEvent.click(screen.getByRole("button", { name: t.gridSave }));
    expect(
      await screen.findByText(
        "Cumul incompatible : Acheteur exécute et autorise “Émettre le bon de commande”",
      ),
    ).toBeInTheDocument();
    expect(screen.getByText("Tâche sans acteur : Payer")).toBeInTheDocument();
    expect(sent.cellules).toEqual([{ tache: 0, acteur: 0, roles: ["EXECUTE", "AUTORISE"] }]);
  });

  it("shows the 422 cellules error under the grid", async () => {
    open({
      grids: [aGrid({ taches: ["T"], acteurs: ["A"] })],
      extra: [
        http.post(`${API_URL}/api/v1/segregation-grids/`, () =>
          HttpResponse.json(
            { detail: "Refusé", errors: { cellules: ["Indice de tâche hors de la grille : 4."] } },
            { status: 422 },
          ),
        ),
      ],
    });
    await userEvent.click(await screen.findByRole("button", { name: t.gridSave }));
    const alert = await screen.findByText("Indice de tâche hors de la grille : 4.");
    expect(alert.closest("[role=alert]")).toBeInTheDocument();
  });

  it("is read-only without contribuer_iii: no active field, no disabled control", async () => {
    open({
      contribuer: false,
      questionnaires: [aQuestionnaire()],
      questions: [aQuestion(1, { appreciation: "NON", reponse: "Écart", repondue: true })],
      grids: [
        aGrid({
          taches: ["T"],
          acteurs: ["A"],
          cellules: [{ tache: 0, acteur: 0, roles: ["EXECUTE"] }],
        }),
      ],
    });
    expect(await screen.findByText("Écart")).toBeInTheDocument();
    expect(screen.queryByRole("textbox")).not.toBeInTheDocument();
    expect(screen.queryByRole("combobox")).not.toBeInTheDocument();
    expect(screen.queryByRole("checkbox")).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: t.gridSave })).not.toBeInTheDocument();
    expect(document.querySelector(":disabled:not(button)")).toBeNull();
  });

  it("hides action buttons when printing", async () => {
    open({ questionnaires: [aQuestionnaire()], questions: [aQuestion(1)] });
    const save = await screen.findByRole("button", { name: t.saveQuestion });
    expect(save.parentElement).toHaveClass("print:hidden");
    expect(screen.getByRole("button", { name: t.gridAddTask }).parentElement).toHaveClass(
      "print:hidden",
    );
    expect(screen.getByText(t.flowNote)).toBeInTheDocument();
  });

  it("removes a question after confirmation and has no axe violation with the dialog open", async () => {
    let deleted = false;
    open({
      questionnaires: [aQuestionnaire()],
      questions: [aQuestion(1)],
      extra: [
        http.delete(`${API_URL}/api/v1/analysis-questions/:id/`, () => {
          deleted = true;
          return new HttpResponse(null, { status: 204 });
        }),
      ],
    });
    await userEvent.click(
      await screen.findByRole("button", { name: `${t.removeQuestion} : Question 1` }),
    );
    const dialog = await screen.findByRole("alertdialog");
    const results = await axe(document.body, NO_CONTRAST);
    expect(results.violations).toEqual([]);
    await userEvent.click(within(dialog).getByRole("checkbox"));
    await userEvent.click(within(dialog).getByRole("button", { name: t.removeQuestion }));
    await waitFor(() => expect(deleted).toBe(true));
  });
});
