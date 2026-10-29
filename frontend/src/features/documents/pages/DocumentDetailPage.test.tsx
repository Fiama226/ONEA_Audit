import { screen, waitFor } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";
import { axe } from "vitest-axe";
import type { Role } from "@/auth/types";
import { fr } from "@/i18n/fr";
import { API_URL, server } from "@/test/msw";
import { renderRoutes } from "@/test/shell";
import { documentRoutes } from "../routes";
import { aDocument, aVersion, DOC_ID, VERSION_ID } from "../testUtils";

const t = fr.documentsRegistre;

type Doc = ReturnType<typeof aDocument>;
type Opts = { doc?: Doc; versions?: ReturnType<typeof aVersion>[] };

function serve({ doc = aDocument(), versions = [aVersion()] }: Opts = {}) {
  let calls = 0;
  server.use(
    // Le document reflète la dernière version déjà servie par l'interrogation.
    http.get(`${API_URL}/api/v1/documents/${DOC_ID}/`, () => {
      const v = versions[Math.max(0, Math.min(calls, versions.length) - 1)] ?? aVersion();
      return HttpResponse.json({
        ...doc,
        derniere_version: {
          id: v.id,
          numero_version: v.numero_version,
          statut: v.statut,
          statut_pdf: v.statut_pdf,
          genere_le: v.genere_le,
        },
        versions: [v],
      });
    }),
    http.get(`${API_URL}/api/v1/document-versions/${VERSION_ID}/`, () => {
      const v = versions[Math.min(calls, versions.length - 1)];
      calls += 1;
      return HttpResponse.json(v);
    }),
    http.get(`${API_URL}/api/v1/document-versions/${VERSION_ID}/consultations/`, () =>
      HttpResponse.json({
        count: 1,
        next: null,
        previous: null,
        results: [
          {
            utilisateur: aVersion().demandee_par,
            le: "2026-03-06T10:15:00Z",
            format: "PDF",
            adresse_ip: "10.0.0.7",
          },
        ],
      }),
    ),
  );
}

function renderDetail(role: Role) {
  return renderRoutes([{ path: "/documents", children: documentRoutes }], role, {
    path: `/documents/${DOC_ID}`,
  });
}

describe("DocumentDetailPage", () => {
  it("shows header, versions and consultations to the RAI", async () => {
    serve();
    const { container } = renderDetail("RAI");
    expect(
      await screen.findByRole("heading", { level: 1, name: "OM-2026-001" }),
    ).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /MI-2026-001/ })).toHaveAttribute(
      "href",
      expect.stringContaining("/missions/"),
    );
    expect(screen.getByRole("heading", { level: 2, name: t.versionsHeading })).toBeInTheDocument();
    expect(await screen.findByText("10.0.0.7")).toBeInTheDocument();
    expect(screen.getByRole("columnheader", { name: t.colIp })).toBeInTheDocument();
    expect(
      (await axe(container, { rules: { "color-contrast": { enabled: false } } })).violations,
    ).toEqual([]);
  });

  it.each<Role>(["AUDITEUR", "AUDITE"])("hides consultations from %s", async (role) => {
    serve();
    renderDetail(role);
    await screen.findByRole("heading", { level: 1, name: "OM-2026-001" });
    expect(screen.queryByRole("heading", { name: t.consultationsHeading })).not.toBeInTheDocument();
    expect(screen.queryByText("10.0.0.7")).not.toBeInTheDocument();
  });

  it("polls an in-progress version until it is ready", async () => {
    const running = aVersion({ statut: "EN_COURS", statut_pdf: "NON_DEMANDE", genere_le: null });
    serve({
      doc: aDocument({
        derniere_version: {
          id: VERSION_ID,
          numero_version: 1,
          statut: "EN_COURS",
          statut_pdf: "NON_DEMANDE",
          genere_le: null,
        },
        versions: [running],
      }),
      versions: [running, aVersion()],
    });
    renderDetail("AUDITEUR");
    expect((await screen.findAllByText(fr.documents.generating)).length).toBeGreaterThan(0);
    await waitFor(
      () => expect(screen.queryByText(fr.documents.generating)).not.toBeInTheDocument(),
      {
        timeout: 8000,
      },
    );
    expect(screen.getAllByText("Prête").length).toBeGreaterThan(0);
  }, 20000);

  it("hides actions when printing", async () => {
    serve();
    renderDetail("RAI");
    const button = await screen.findByRole("button", { name: fr.documents.downloadWord });
    expect(button.closest(".print\\:hidden")).not.toBeNull();
    expect(
      screen.getByRole("link", { name: t.backToList }).closest(".print\\:hidden"),
    ).not.toBeNull();
  });

  it("shows a not-found message for a 404", async () => {
    server.use(
      http.get(`${API_URL}/api/v1/documents/${DOC_ID}/`, () =>
        HttpResponse.json({ detail: "Introuvable." }, { status: 404 }),
      ),
    );
    renderDetail("AUDITE");
    expect(await screen.findByText(t.notFound)).toBeInTheDocument();
  });
});
