import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";
import { axe } from "vitest-axe";
import type { Role } from "@/auth/types";
import { fr } from "@/i18n/fr";
import { appRoutes } from "@/routes";
import { API_URL, server } from "@/test/msw";
import { allowSlowShell, renderRoutes } from "@/test/shell";
import { documentRoutes } from "../routes";
import type { DocumentListe } from "../types";
import { DOC_ID, MISSION_ID, VERSION_ID } from "../testUtils";

allowSlowShell();
const t = fr.documentsRegistre;

function row(i: number): DocumentListe {
  return {
    id: i === 1 ? DOC_ID : `00000000-0000-4000-8000-${String(i).padStart(12, "0")}`,
    type_document: "ORDRE_MISSION",
    type_document_libelle: "Ordre de mission",
    numero: `OM-2026-${String(i).padStart(3, "0")}`,
    mission: { id: MISSION_ID, reference: "MI-2026-001", titre: "Audit des achats" },
    derniere_version: {
      id: VERSION_ID,
      numero_version: 2,
      statut: "PRETE",
      statut_pdf: "PRET",
      genere_le: "2026-03-05T09:00:30Z",
    },
    nombre_versions: 2,
  };
}

const TYPES = [
  { code: "ORDRE_MISSION", libelle: "Ordre de mission" },
  { code: "RAPPORT", libelle: "Rapport" },
];

function serve(total: number, seen: string[] = []) {
  server.use(
    http.get(`${API_URL}/api/v1/document-types/`, () => HttpResponse.json(TYPES)),
    http.get(`${API_URL}/api/v1/document-versions/${VERSION_ID}/consultations/`, () =>
      HttpResponse.json({ count: 4, next: null, previous: null, results: [] }),
    ),
    http.get(`${API_URL}/api/v1/documents/`, ({ request }) => {
      const url = new URL(request.url);
      seen.push(url.search);
      const page = Number(url.searchParams.get("page") ?? 1);
      const size = Number(url.searchParams.get("page_size") ?? 20);
      const start = (page - 1) * size;
      const results = Array.from({ length: Math.max(0, Math.min(size, total - start)) }, (_, i) =>
        row(start + i + 1),
      );
      return HttpResponse.json({ count: total, next: null, previous: null, results });
    }),
  );
}

function renderList(role: Role, path = "/documents") {
  return renderRoutes([{ path: "/documents", children: documentRoutes }], role, { path });
}

describe("DocumentListPage", () => {
  it("pages through 201 documents with the standard pagination", async () => {
    const seen: string[] = [];
    serve(201, seen);
    const user = userEvent.setup();
    const { container } = renderList("RAI");
    expect(await screen.findByRole("link", { name: "OM-2026-001" })).toBeInTheDocument();
    expect(screen.getAllByText(/201 résultats/).length).toBeGreaterThan(0);
    expect(screen.getByText(/Page 1 sur 11/)).toBeInTheDocument();
    expect((await screen.findAllByText("4")).length).toBeGreaterThan(0);
    expect(screen.getAllByText("Prête").length).toBeGreaterThan(0);
    expect(
      (await axe(container, { rules: { "color-contrast": { enabled: false } } })).violations,
    ).toEqual([]);
    await user.click(screen.getByRole("button", { name: fr.table.nextPage }));
    expect(await screen.findByRole("link", { name: "OM-2026-021" })).toBeInTheDocument();
    expect(seen.some((s) => s.includes("page=2"))).toBe(true);
  });

  it("reflects the type filter in the URL and resets the page", async () => {
    const seen: string[] = [];
    serve(30, seen);
    const user = userEvent.setup();
    const { router } = renderList("RAI", "/documents?page=2");
    await screen.findByRole("link", { name: "OM-2026-021" });
    await screen.findByRole("option", { name: "Rapport" });
    await user.selectOptions(screen.getByLabelText(t.typeLabel), "RAPPORT");
    await waitFor(() => expect(router.state.location.search).toBe("?type=RAPPORT"));
    await waitFor(() => expect(seen.at(-1)).toContain("type_document=RAPPORT"));
    expect(seen.at(-1)).toContain("page=1");
    expect(screen.getByLabelText(t.typeLabel)).toHaveValue("RAPPORT");
  });

  it("drops an unknown type from the request and caps the search at 100 characters", async () => {
    const seen: string[] = [];
    serve(1, seen);
    renderList("RAI", `/documents?type=PIRATE&q=${"x".repeat(150)}`);
    await screen.findByRole("link", { name: "OM-2026-001" });
    await waitFor(() => expect(screen.getByLabelText(t.typeLabel)).toHaveValue(""));
    expect(seen.at(-1)).not.toContain("PIRATE");
    expect(screen.getByLabelText(t.searchLabel)).toHaveAttribute("maxlength", "100");
    expect((screen.getByLabelText(t.searchLabel) as HTMLInputElement).value).toHaveLength(100);
  });

  it.each<[Role, string]>([
    ["RAI", t.emptyRai],
    ["AUDITEUR", t.emptyAuditeur],
    ["AUDITE", t.emptyAudite],
  ])("shows the empty state of %s", async (role, text) => {
    serve(0);
    renderList(role);
    expect(await screen.findByText(text)).toBeInTheDocument();
  });

  it("shows an error with retry, never an empty state, when loading fails", async () => {
    serve(0);
    server.use(
      http.get(`${API_URL}/api/v1/documents/`, () => HttpResponse.json({}, { status: 500 })),
    );
    renderList("AUDITEUR");
    expect(await screen.findByText(t.loadError)).toBeInTheDocument();
    expect(screen.queryByText(t.emptyRai)).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: fr.common.retry })).toBeInTheDocument();
  });

  it("does not request consultations for an audité", async () => {
    serve(1);
    let called = false;
    server.use(
      http.get(`${API_URL}/api/v1/document-versions/${VERSION_ID}/consultations/`, () => {
        called = true;
        return HttpResponse.json({}, { status: 403 });
      }),
    );
    renderList("AUDITE");
    const r = (await screen.findByRole("link", { name: "OM-2026-001" })).closest("tr")!;
    expect(within(r).getByText("v2")).toBeInTheDocument();
    expect(called).toBe(false);
  });

  it.each<Role>(["ADMIN", "DG"])("denies %s access to /documents", async (role) => {
    serve(1);
    renderRoutes(appRoutes, role, { path: "/documents" });
    expect(await screen.findByText(fr.errors.forbiddenText)).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "OM-2026-001" })).not.toBeInTheDocument();
  });
});
