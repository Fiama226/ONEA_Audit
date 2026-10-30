import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { describe, expect, it, vi } from "vitest";
import { fr } from "@/i18n/fr";
import { downloadBlob } from "@/lib/download";
import { API_URL, server } from "@/test/msw";
import { renderRoutes } from "@/test/shell";
import { aRapportDiffuse, RAPPORT_ID } from "../testUtils";
import type { RapportDiffuse } from "../types";
import { RapportDiffusePage } from "./RapportDiffusePage";

vi.mock("@/lib/download", () => ({ downloadBlob: vi.fn() }));

const t = fr.rapportFinal;

function renderDetail(rapport: RapportDiffuse) {
  server.use(
    http.get(`${API_URL}/api/v1/reports/${RAPPORT_ID}/`, () => HttpResponse.json(rapport)),
  );
  return renderRoutes([{ path: "/rapports/:id", element: <RapportDiffusePage /> }], "DG", {
    path: `/rapports/${RAPPORT_ID}`,
  });
}

describe("RapportDiffusePage", () => {
  it("affiche la synthèse, l'appréciation et la mention de correction", async () => {
    renderDetail(
      aRapportDiffuse({ mention_correction: "Rapport corrigé (version 2) : erreur de chiffre" }),
    );
    expect(await screen.findByText("Le dispositif d'achat est perfectible.")).toBeInTheDocument();
    expect(screen.getAllByText("Perfectible").length).toBeGreaterThan(0);
    expect(screen.getByText(/Rapport corrigé \(version 2\)/)).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /mission/i })).not.toBeInTheDocument();
  });

  it("télécharge par l'API authentifiée (downloadReport)", async () => {
    let url: URL | undefined;
    const user = userEvent.setup();
    server.use(
      http.get(`${API_URL}/api/v1/reports/${RAPPORT_ID}/download/`, ({ request }) => {
        url = new URL(request.url);
        return new HttpResponse("%PDF-", {
          headers: { "Content-Disposition": 'attachment; filename="rapport.pdf"' },
        });
      }),
    );
    renderDetail(aRapportDiffuse());
    await user.click(await screen.findByRole("button", { name: t.downloadNotePdf }));
    await waitFor(() => expect(downloadBlob).toHaveBeenCalled());
    expect(url?.searchParams.get("format")).toBe("pdf");
    expect(url?.searchParams.get("document")).toBe("note");
  });

  it("affiche le message d'intégrité sur un 409", async () => {
    const user = userEvent.setup();
    server.use(
      http.get(`${API_URL}/api/v1/reports/${RAPPORT_ID}/download/`, () =>
        HttpResponse.json({ detail: "x" }, { status: 409 }),
      ),
    );
    renderDetail(aRapportDiffuse());
    await user.click(await screen.findByRole("button", { name: t.downloadReportWord }));
    expect(await screen.findByRole("alert")).toHaveTextContent(fr.documents.integrityError);
  });

  it("enregistre l'accusé de réception après confirmation", async () => {
    let called = false;
    const user = userEvent.setup();
    server.use(
      http.post(`${API_URL}/api/v1/reports/${RAPPORT_ID}/acknowledge/`, () => {
        called = true;
        return HttpResponse.json(aRapportDiffuse({ mon_accuse_reception: "2026-10-30T08:00:00Z" }));
      }),
    );
    renderDetail(aRapportDiffuse({ actions_possibles: ["ACCUSER_RECEPTION"] }));
    await user.click(await screen.findByRole("button", { name: t.acknowledge }));
    await user.click(screen.getByRole("checkbox", { name: fr.missions.confirmCheckbox }));
    await user.click(screen.getByRole("button", { name: t.acknowledgeConfirm }));
    await waitFor(() => expect(called).toBe(true));
  });

  it("n'affiche pas l'accusé quand il est déjà donné", async () => {
    renderDetail(
      aRapportDiffuse({
        actions_possibles: ["ACCUSER_RECEPTION"],
        mon_accuse_reception: "2026-10-30T08:00:00Z",
      }),
    );
    expect(
      await screen.findByText("Accusé de réception enregistré le 30/10/2026."),
    ).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: t.acknowledge })).not.toBeInTheDocument();
  });
});
