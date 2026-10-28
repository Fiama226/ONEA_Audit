import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { axe } from "vitest-axe";
import { describe, expect, it } from "vitest";
import { fr } from "@/i18n/fr";
import { API_URL, server } from "@/test/msw";
import { UserHistory } from "./UserHistory";

const ENTRY = {
  id: 1,
  timestamp: "2026-10-28T08:00:00Z",
  actor: { id: 2, username: "admin" },
  action: "update",
  model: "users.user",
  object_id: "7",
  object_repr: "auditeur2",
  changes: { is_active: ["True", "False"] },
};

const paged = (results: object[], count = results.length) => ({
  count,
  next: null,
  previous: null,
  results,
});

function renderHistory() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <UserHistory userId={7} />
    </QueryClientProvider>,
  );
}

describe("UserHistory", () => {
  it("requests the audit log of the user and renders entries", async () => {
    let search = "";
    server.use(
      http.get(`${API_URL}/api/v1/audit-log/`, ({ request }) => {
        search = new URL(request.url).search;
        return HttpResponse.json(paged([ENTRY]));
      }),
    );
    const { container } = renderHistory();
    expect(await screen.findByText("28/10/2026 08:00")).toBeInTheDocument();
    expect(search).toBe("?model=users.user&object_id=7&page=1");
    expect(screen.getByText("admin")).toBeInTheDocument();
    expect(screen.getByText("Modification")).toBeInTheDocument();
    const item = screen.getByRole("listitem");
    expect(item).toHaveTextContent(/Statut du compte : Actif.*→.*Désactivé/);
    expect(item).toHaveTextContent("devient");
    const results = await axe(container, { rules: { "color-contrast": { enabled: false } } });
    expect(results.violations).toEqual([]);
  });

  it("shows Système when the actor is null", async () => {
    server.use(
      http.get(`${API_URL}/api/v1/audit-log/`, () =>
        HttpResponse.json(paged([{ ...ENTRY, actor: null, action: "create" }])),
      ),
    );
    renderHistory();
    expect(await screen.findByText("Système")).toBeInTheDocument();
    expect(screen.getByText("Création")).toBeInTheDocument();
  });

  it("goes to page 2 on Suivant", async () => {
    const pages: string[] = [];
    server.use(
      http.get(`${API_URL}/api/v1/audit-log/`, ({ request }) => {
        pages.push(new URL(request.url).searchParams.get("page") ?? "");
        return HttpResponse.json(paged([ENTRY], 40));
      }),
    );
    renderHistory();
    await screen.findByText("28/10/2026 08:00");
    await userEvent.click(screen.getByRole("button", { name: fr.table.nextPage }));
    await screen.findByText(/Page 2 sur 2/);
    expect(pages).toContain("2");
  });

  it("shows the empty state", async () => {
    server.use(http.get(`${API_URL}/api/v1/audit-log/`, () => HttpResponse.json(paged([]))));
    renderHistory();
    expect(
      await screen.findByText("Aucune modification enregistrée pour ce compte."),
    ).toBeInTheDocument();
  });

  it("shows an error alert on failure", async () => {
    server.use(
      http.get(`${API_URL}/api/v1/audit-log/`, () => HttpResponse.json({}, { status: 500 })),
    );
    renderHistory();
    expect(await screen.findByRole("alert")).toHaveTextContent(fr.errors.generic);
  });
});
