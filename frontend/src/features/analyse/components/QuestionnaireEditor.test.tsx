import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";
import type { paths } from "@/api/schema";
import { fr } from "@/i18n/fr";
import { API_URL, server } from "@/test/msw";
import { aQuestionnaire } from "../testUtils";
import type { Question } from "../types";
import { QuestionnaireEditor } from "./QuestionnaireEditor";

const t = fr.analyseIII;

type QuestionList =
  paths["/api/v1/analysis-questions/"]["get"]["responses"][200]["content"]["application/json"];

function q(n: number, overrides: Partial<Question> = {}): Question {
  return {
    id: `q-${n}`,
    questionnaire: "66666666-6666-4666-8666-666666666666",
    theme: n === 1 ? "Organisation" : "Systèmes",
    libelle: `Question ${n}`,
    reponse: "",
    appreciation: "",
    ordre: n,
    repondue: false,
    ...overrides,
  };
}

function setup(questions: Question[], editable: boolean) {
  const state = { questions };
  server.use(
    // L'API renvoie un tableau nu (vue non paginée) : le mock suit le contrat OpenAPI.
    http.get(`${API_URL}/api/v1/analysis-questions/`, () =>
      HttpResponse.json(state.questions satisfies QuestionList),
    ),
  );
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  render(
    <QueryClientProvider client={client}>
      <QuestionnaireEditor
        questionnaire={aQuestionnaire()}
        editable={editable}
        missionReference="MI-2026-001"
      />
    </QueryClientProvider>,
  );
  return state;
}

describe("QuestionnaireEditor", () => {
  it("groups questions by theme and shows the counter and the print header", async () => {
    setup([q(1), q(2, { repondue: true, appreciation: "OUI" })], true);
    expect(await screen.findByText("1 / 2 questions renseignées")).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "Organisation" })).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "Systèmes" })).toBeInTheDocument();
    expect(screen.getByText("Mission MI-2026-001")).toBeInTheDocument();
    expect(screen.getByText("Questionnaire de prise de connaissance")).toBeInTheDocument();
  });

  it("shows an error state, not an empty one, when loading fails", async () => {
    server.use(
      http.get(`${API_URL}/api/v1/analysis-questions/`, () =>
        HttpResponse.json({ detail: "x", errors: {} }, { status: 500 }),
      ),
    );
    render(
      <QueryClientProvider
        client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}
      >
        <QuestionnaireEditor questionnaire={aQuestionnaire()} editable />
      </QueryClientProvider>,
    );
    expect(await screen.findByRole("alert")).toHaveTextContent(t.loadError);
    expect(screen.queryByText(t.noQuestion)).not.toBeInTheDocument();
  });

  it("adds a question with the next order", async () => {
    let body: unknown;
    server.use(
      http.post(`${API_URL}/api/v1/analysis-questions/`, async ({ request }) => {
        body = await request.json();
        return HttpResponse.json(q(9), { status: 201 });
      }),
    );
    setup([q(1)], true);
    await userEvent.type(await screen.findByLabelText(t.theme), "Finance");
    await userEvent.type(screen.getByLabelText(t.question), "Existe-t-il un budget ?");
    await userEvent.click(screen.getByRole("button", { name: t.addQuestion }));
    await waitFor(() =>
      expect(body).toEqual({
        questionnaire: "66666666-6666-4666-8666-666666666666",
        ordre: 2,
        theme: "Finance",
        libelle: "Existe-t-il un budget ?",
      }),
    );
  });

  it("validates the new question fields", async () => {
    setup([], true);
    await userEvent.click(await screen.findByRole("button", { name: t.addQuestion }));
    expect(await screen.findByText(t.themeRequired)).toBeInTheDocument();
    expect(screen.getByText(t.questionRequired)).toBeInTheDocument();
  });

  it("drops a removed question from the list without waiting for a refetch", async () => {
    const state = setup([q(1), q(2)], true);
    server.use(
      http.delete(`${API_URL}/api/v1/analysis-questions/:id/`, () => {
        state.questions = state.questions.filter((x) => x.id !== "q-1");
        return new HttpResponse(null, { status: 204 });
      }),
    );
    await userEvent.click(
      await screen.findByRole("button", { name: `${t.removeQuestion} : Question 1` }),
    );
    const dialog = await screen.findByRole("alertdialog");
    await userEvent.click(within(dialog).getByRole("checkbox"));
    await userEvent.click(within(dialog).getByRole("button", { name: t.removeQuestion }));
    await waitFor(() => expect(screen.queryByText("Question 1")).not.toBeInTheDocument());
    expect(screen.getByText("Question 2")).toBeInTheDocument();
  });

  it("is read-only when not editable", async () => {
    setup([q(1, { appreciation: "NON", reponse: "Écart", repondue: true })], false);
    expect(await screen.findByText("Écart")).toBeInTheDocument();
    expect(screen.queryByRole("textbox")).not.toBeInTheDocument();
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
  });
});
