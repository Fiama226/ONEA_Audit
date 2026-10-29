import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import { axe } from "vitest-axe";
import { API_URL, server } from "@/test/msw";
import { renderWithAuth } from "@/test/shell";
import { aReport } from "../testUtils";
import { ImportDirectoryDialog } from "./ImportDirectoryDialog";

const SEARCH_URL = `${API_URL}/api/v1/user-accounts/directory-search/`;
const SEARCH_LABEL = "Rechercher dans l'annuaire (nom, identifiant, e-mail)";

const entry = (i: number, over: object = {}) => ({
  keycloak_id: `00000000-0000-4000-8000-${String(i).padStart(12, "0")}`,
  username: `user${i}`,
  email: `user${i}@onea.bf`,
  nom_complet: `Agent ${i}`,
  direction: "DAI",
  fonction: "Auditeur",
  compte_id: null,
  ...over,
});

function renderDialog() {
  return renderWithAuth(<ImportDirectoryDialog open onOpenChange={() => {}} />, "ADMIN");
}

async function search(term = "aud") {
  await userEvent.type(screen.getByLabelText(SEARCH_LABEL), term);
}

describe("ImportDirectoryDialog", () => {
  it("does not query below 2 characters and queries once after the debounce", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    try {
      const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
      const queries: string[] = [];
      server.use(
        http.get(SEARCH_URL, ({ request }) => {
          queries.push(new URL(request.url).search);
          return HttpResponse.json([entry(1)]);
        }),
      );
      renderDialog();
      await user.type(screen.getByLabelText(SEARCH_LABEL), "a");
      await vi.advanceTimersByTimeAsync(1000);
      expect(queries).toEqual([]);
      await user.type(screen.getByLabelText(SEARCH_LABEL), "ud");
      expect(await screen.findByText("Agent 1", {}, { timeout: 15000 })).toBeInTheDocument();
      expect(queries).toEqual(["?q=aud"]);
    } finally {
      vi.useRealTimers();
    }
  });

  it("disables entries already present and links to their record", async () => {
    server.use(
      http.get(SEARCH_URL, () => HttpResponse.json([entry(1, { compte_id: 9 }), entry(2)])),
    );
    renderDialog();
    await search();
    expect(await screen.findByRole("checkbox", { name: "Sélectionner Agent 1" })).toBeDisabled();
    expect(screen.getByRole("checkbox", { name: "Sélectionner Agent 2" })).toBeEnabled();
    expect(screen.getByRole("link", { name: "Déjà présent" })).toHaveAttribute(
      "href",
      "/administration/utilisateurs/9",
    );
  });

  it("refuses a 51st selection", async () => {
    server.use(
      http.get(SEARCH_URL, () =>
        HttpResponse.json(Array.from({ length: 51 }, (_, i) => entry(i + 1))),
      ),
    );
    renderDialog();
    await search();
    await screen.findByText("Agent 51");
    // Requêtes ARIA coûteuses sur 51 lignes : on récupère les cases une seule fois.
    const boxes = screen.getAllByRole("checkbox");
    expect(boxes).toHaveLength(51);
    for (const box of boxes.slice(0, 50)) fireEvent.click(box);
    const last = boxes[50]!;
    fireEvent.click(last);
    expect(screen.getByText("50 comptes au plus par import.")).toBeInTheDocument();
    expect(last).not.toBeChecked();
    expect(boxes[49]).toBeChecked();
  }, 60000);

  it("imports the checked entries and shows the report", async () => {
    let body: unknown;
    server.use(
      http.get(SEARCH_URL, () => HttpResponse.json([entry(1), entry(2), entry(3)])),
      http.post(`${API_URL}/api/v1/user-accounts/import-directory/`, async ({ request }) => {
        body = await request.json();
        return HttpResponse.json(
          aReport({ dry_run: false, crees: ["user1", "user3"], ignores: [] }),
        );
      }),
    );
    renderDialog();
    await search();
    expect(screen.getByRole("button", { name: "Importer la sélection" })).toBeDisabled();
    await userEvent.click(await screen.findByRole("checkbox", { name: "Sélectionner Agent 1" }));
    await userEvent.click(screen.getByRole("checkbox", { name: "Sélectionner Agent 3" }));
    await userEvent.click(screen.getByRole("button", { name: "Importer la sélection" }));
    expect(await screen.findByText(/2 comptes créés/)).toBeInTheDocument();
    expect(body).toEqual({ keycloak_ids: [entry(1).keycloak_id, entry(3).keycloak_id] });
  });

  it("shows a message when the directory is unavailable (503)", async () => {
    server.use(http.get(SEARCH_URL, () => HttpResponse.json({ detail: "x" }, { status: 503 })));
    renderDialog();
    await search();
    expect(
      await screen.findByText(
        "L'annuaire (Keycloak) est momentanément indisponible. Réessayez plus tard.",
      ),
    ).toBeInTheDocument();
  });

  it("has no axe violation with results displayed", async () => {
    server.use(
      http.get(SEARCH_URL, () => HttpResponse.json([entry(1), entry(2, { compte_id: 4 })])),
    );
    renderDialog();
    await search();
    await screen.findByText("Agent 1");
    const results = await axe(document.body, { rules: { "color-contrast": { enabled: false } } });
    expect(results.violations).toEqual([]);
  });

  it("does not retry a 503 (production client keeps default retries)", async () => {
    let calls = 0;
    server.use(
      http.get(SEARCH_URL, () => {
        calls += 1;
        return HttpResponse.json({ detail: "x" }, { status: 503 });
      }),
    );
    // Client de production : `retry` par défaut (3 tentatives espacées de 1, 2 et 4 s).
    render(
      <QueryClientProvider client={new QueryClient()}>
        <MemoryRouter>
          <ImportDirectoryDialog open onOpenChange={() => {}} />
        </MemoryRouter>
      </QueryClientProvider>,
    );
    await search();
    expect(await screen.findByRole("alert", {}, { timeout: 3000 })).toHaveTextContent(
      "momentanément indisponible",
    );
    expect(calls).toBe(1);
  }, 20000);

  it("lists selections across searches and lets the user remove them", async () => {
    server.use(
      http.get(SEARCH_URL, ({ request }) => {
        const q = new URL(request.url).searchParams.get("q");
        return HttpResponse.json(q === "aud" ? [entry(1)] : [entry(2)]);
      }),
    );
    renderDialog();
    await search();
    fireEvent.click(await screen.findByRole("checkbox", { name: "Sélectionner Agent 1" }));
    await userEvent.clear(screen.getByLabelText(SEARCH_LABEL));
    await userEvent.type(screen.getByLabelText(SEARCH_LABEL), "bob");
    fireEvent.click(await screen.findByRole("checkbox", { name: "Sélectionner Agent 2" }));
    const list = screen.getByRole("list", { name: "Comptes sélectionnés" });
    expect(list).toHaveTextContent("Agent 1");
    expect(list).toHaveTextContent("Agent 2");
    await userEvent.click(screen.getByRole("button", { name: "Retirer Agent 1" }));
    expect(list).not.toHaveTextContent("Agent 1");
    await userEvent.click(screen.getByRole("button", { name: "Vider la sélection" }));
    expect(screen.queryByRole("list", { name: "Comptes sélectionnés" })).not.toBeInTheDocument();
  });

  it("limits the search field to 100 characters", () => {
    renderDialog();
    expect(screen.getByLabelText(SEARCH_LABEL)).toHaveAttribute("maxlength", "100");
  });

  it("focuses the report heading after the import", async () => {
    server.use(
      http.get(SEARCH_URL, () => HttpResponse.json([entry(1)])),
      http.post(`${API_URL}/api/v1/user-accounts/import-directory/`, () =>
        HttpResponse.json(aReport({ dry_run: false, crees: ["user1"], ignores: [] })),
      ),
    );
    renderDialog();
    await search();
    fireEvent.click(await screen.findByRole("checkbox", { name: "Sélectionner Agent 1" }));
    await userEvent.click(screen.getByRole("button", { name: "Importer la sélection" }));
    const heading = await screen.findByRole("heading", { name: "Import terminé" });
    expect(heading).toHaveFocus();
  });
});
