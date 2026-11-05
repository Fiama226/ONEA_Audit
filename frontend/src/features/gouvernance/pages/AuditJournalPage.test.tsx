import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";
import type { Role } from "@/auth/types";
import { API_URL, server } from "@/test/msw";
import { renderRoutes } from "@/test/shell";
import type { AuditLogEntry } from "../api";
import { AuditJournalPage } from "./AuditJournalPage";

const URL = `${API_URL}/api/v1/audit-log/`;

const entry: AuditLogEntry = {
  id: 41,
  timestamp: "2026-11-04T09:30:00Z",
  actor: { id: 1, username: "admin" },
  action: "update",
  model: "gouvernance.reglegouvernance",
  object_id: "7",
  object_repr: "objectivity_check",
  changes: {
    valeur: [
      '{"enabled": true, "mode": "BLOCK", "cooling_off_months": 12}',
      '{"enabled": true, "mode": "WARN", "cooling_off_months": 12}',
    ],
  },
  action_metier: "regle_gouvernance",
  motif: "Effectif réduit en 2026",
  affaiblissement: true,
};

function page(results: AuditLogEntry[]) {
  return { count: results.length, next: null, previous: null, results };
}

function renderPage(role: Role, path = "/journal-audit") {
  return renderRoutes([{ path: "*", element: <AuditJournalPage /> }], role, { path });
}

describe("AuditJournalPage", () => {
  it("shows a rule change with readable before/after values and its reason", async () => {
    const urls: string[] = [];
    server.use(
      http.get(URL, ({ request }) => {
        urls.push(request.url);
        return HttpResponse.json(page([entry]));
      }),
    );
    renderPage("ADMIN", "/journal-audit?categorie=gouvernance");
    expect(await screen.findByText("Règle : Contrôle d'objectivité")).toBeInTheDocument();
    expect(screen.getByText("Effectif réduit en 2026")).toBeInTheDocument();
    expect(screen.getByText("Assouplissement")).toBeInTheDocument();
    expect(screen.getByText(/En cas de situation détectée : Avertir/)).toBeInTheDocument();
    expect(urls.at(-1)).toContain("categorie=gouvernance");
  });

  it("filters by category for the admin", async () => {
    const urls: string[] = [];
    server.use(
      http.get(URL, ({ request }) => {
        urls.push(request.url);
        return HttpResponse.json(page([]));
      }),
    );
    renderPage("RAI");
    expect(await screen.findByText("Aucune entrée pour ces critères.")).toBeInTheDocument();
    expect(urls.at(-1)).not.toContain("categorie");
    await userEvent.selectOptions(screen.getByLabelText("Catégorie"), "gouvernance");
    await screen.findByText("Aucune entrée pour ces critères.");
    expect(urls.at(-1)).toContain("categorie=gouvernance");
  });

  it("always asks for governance entries for the DG, without the category filter", async () => {
    const urls: string[] = [];
    server.use(
      http.get(URL, ({ request }) => {
        urls.push(request.url);
        return HttpResponse.json(page([entry]));
      }),
    );
    renderPage("DG");
    await screen.findByText("Règle : Contrôle d'objectivité");
    expect(screen.queryByLabelText("Catégorie")).not.toBeInTheDocument();
    expect(urls.at(-1)).toContain("categorie=gouvernance");
  });
});
