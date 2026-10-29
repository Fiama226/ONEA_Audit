import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";
import { aMission } from "@/features/missions/testUtils";
import { fr } from "@/i18n/fr";
import { API_URL, server } from "@/test/msw";
import { aQuestionnaire } from "../testUtils";
import { QciSection } from "./QciSection";

const t = fr.analyseIII;
const PROCESS = { id: "88888888-8888-4888-8888-888888888888", code: "P-ACH", libelle: "Achats" };

function setup(editable: boolean, qcis: ReturnType<typeof aQuestionnaire>[]) {
  server.use(
    http.get(`${API_URL}/api/v1/analysis-questionnaires/`, () =>
      HttpResponse.json({ count: qcis.length, next: null, previous: null, results: qcis }),
    ),
    http.get(`${API_URL}/api/v1/analysis-questions/`, () =>
      HttpResponse.json({ count: 0, next: null, previous: null, results: [] }),
    ),
  );
  render(
    <QueryClientProvider
      client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}
    >
      <QciSection mission={aMission({ processus_detail: [PROCESS] })} editable={editable} />
    </QueryClientProvider>,
  );
}

describe("QciSection", () => {
  it("creates the QCI of a process when editable", async () => {
    let body: unknown;
    server.use(
      http.post(`${API_URL}/api/v1/analysis-questionnaires/`, async ({ request }) => {
        body = await request.json();
        return HttpResponse.json(aQuestionnaire({ type: "QCI" }), { status: 201 });
      }),
    );
    setup(true, []);
    await userEvent.click(await screen.findByRole("button", { name: `${t.createQci} : P-ACH` }));
    await waitFor(() =>
      expect(body).toEqual({
        mission: "11111111-1111-4111-8111-111111111111",
        type: "QCI",
        processus: PROCESS.id,
      }),
    );
  });

  it("offers no creation when not editable", async () => {
    setup(false, []);
    expect(await screen.findByText(t.noQuestionnaire)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Créer le QCI/ })).not.toBeInTheDocument();
  });

  it("renders the editor of an existing QCI", async () => {
    setup(false, [aQuestionnaire({ type: "QCI", processus: PROCESS.id })]);
    expect(await screen.findByText("0 / 0 questions renseignées")).toBeInTheDocument();
  });
});
