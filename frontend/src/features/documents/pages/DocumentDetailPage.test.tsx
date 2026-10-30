import { act, screen, waitFor } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { describe, expect, it, vi } from "vitest";
import { GENERATION_TIMEOUT_MESSAGE, POLL_TIMEOUT_MS } from "../api";
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

  it("does not refetch the document when the version is already ready", async () => {
    serve();
    let docCalls = 0;
    let versionCalls = 0;
    server.use(
      http.get(`${API_URL}/api/v1/documents/${DOC_ID}/`, () => {
        docCalls += 1;
        return HttpResponse.json(aDocument());
      }),
      http.get(`${API_URL}/api/v1/document-versions/${VERSION_ID}/`, () => {
        versionCalls += 1;
        return HttpResponse.json(aVersion());
      }),
    );
    renderDetail("AUDITEUR");
    await screen.findByRole("heading", { level: 1, name: "OM-2026-001" });
    await waitFor(() => expect(versionCalls).toBe(1));
    await new Promise((r) => setTimeout(r, 300));
    expect(docCalls).toBe(1);
  });

  it("shows a visible alert with a retry once the polling budget is spent", async () => {
    const running = aVersion({ statut: "EN_COURS", statut_pdf: "NON_DEMANDE", genere_le: null });
    let versionCalls = 0;
    serve({ versions: [running] });
    server.use(
      http.get(`${API_URL}/api/v1/document-versions/${VERSION_ID}/`, () => {
        versionCalls += 1;
        return HttpResponse.json(running);
      }),
    );
    vi.useFakeTimers({ shouldAdvanceTime: true });
    try {
      renderDetail("AUDITEUR");
      expect((await screen.findAllByText(fr.documents.generating)).length).toBeGreaterThan(0);
      await act(async () => {
        await vi.advanceTimersByTimeAsync(POLL_TIMEOUT_MS + 1000);
      });
      const alert = await screen.findByRole("alert");
      expect(alert).toHaveTextContent(GENERATION_TIMEOUT_MESSAGE);
      expect(alert).not.toHaveClass("text-xs");
      const stopped = versionCalls;
      await act(async () => {
        await vi.advanceTimersByTimeAsync(10_000);
      });
      expect(versionCalls - stopped).toBeLessThanOrEqual(1);

      await act(async () => {
        screen.getByRole("button", { name: fr.common.retry }).click();
        await vi.advanceTimersByTimeAsync(5_000);
      });
      expect(versionCalls).toBeGreaterThan(stopped);
      await waitFor(() => expect(screen.queryByRole("alert")).not.toBeInTheDocument());
    } finally {
      vi.useRealTimers();
    }
  }, 30000);

  it("hides actions when printing", async () => {
    serve();
    renderDetail("RAI");
    const button = await screen.findByRole("button", { name: fr.documents.downloadWord });
    expect(button.closest(".print\\:hidden")).not.toBeNull();
    expect(
      screen.getByRole("button", { name: fr.documents.downloadPdf }).closest(".print\\:hidden"),
    ).not.toBeNull();
    for (const nav of screen.getAllByRole("navigation")) {
      expect(nav.closest(".print\\:hidden")).not.toBeNull();
    }
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
