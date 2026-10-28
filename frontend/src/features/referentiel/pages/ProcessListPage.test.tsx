import { configure, screen, waitFor } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { axe } from "vitest-axe";
import { beforeAll, describe, expect, it, vi } from "vitest";
import { fr } from "@/i18n/fr";
import { API_URL, server } from "@/test/msw";
import { page, renderReferentiel } from "./testUtils";

const s = fr.refStructure;

beforeAll(() => {
  vi.setConfig({ testTimeout: 20000 });
  configure({ asyncUtilTimeout: 4000 });
});

function serve(results: object[]) {
  server.use(http.get(`${API_URL}/api/v1/processes/`, () => HttpResponse.json(page(results))));
}

const PROCESS = {
  id: "p1",
  code: "FEP",
  libelle: "Fournir l'eau potable",
  famille: "REALISATION",
  ordre: 4,
  directions_detail: [{ id: "d1", code: "DEX", libelle: "Exploitation" }],
};

describe("ProcessListPage", () => {
  it("shows the empty state with a create action for a RAI", async () => {
    serve([]);
    renderReferentiel("/referentiel/processus", "RAI");
    expect(await screen.findByText(s.processEmptyEditorTitle)).toBeInTheDocument();
    expect(screen.getByText(s.processEmptyEditorHelp)).toBeInTheDocument();
    expect(screen.getAllByRole("link", { name: s.createProcess }).length).toBeGreaterThan(0);
  });

  it("shows a message without any button for an AUDITEUR", async () => {
    serve([]);
    renderReferentiel("/referentiel/processus", "AUDITEUR");
    expect(await screen.findByText(s.processEmptyReaderTitle)).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: s.createProcess })).not.toBeInTheDocument();
  });

  it("lists processes and reflects the family filter in the URL", async () => {
    serve([PROCESS]);
    const { router } = renderReferentiel("/referentiel/processus", "ADMIN");
    expect(await screen.findByRole("link", { name: PROCESS.libelle })).toBeInTheDocument();
    expect(screen.getByText("DEX")).toBeInTheDocument();
    const { default: userEvent } = await import("@testing-library/user-event");
    await userEvent.selectOptions(screen.getByLabelText(s.familyFilter), "SUPPORT");
    await waitFor(() => expect(router.state.location.search).toContain("famille=SUPPORT"));
  });

  it("shows an error alert instead of the empty state when loading fails", async () => {
    server.use(
      http.get(`${API_URL}/api/v1/processes/`, () => HttpResponse.json({}, { status: 500 })),
    );
    renderReferentiel("/referentiel/processus", "RAI");
    expect(await screen.findByRole("alert")).toHaveTextContent(s.loadError);
    expect(screen.queryByText(s.processEmptyEditorTitle)).not.toBeInTheDocument();
  });

  it("has no accessibility violation", async () => {
    serve([PROCESS]);
    const { container } = renderReferentiel("/referentiel/processus", "RAI");
    await screen.findByRole("link", { name: PROCESS.libelle });
    const results = await axe(container, { rules: { "color-contrast": { enabled: false } } });
    expect(results.violations).toEqual([]);
  });
});
