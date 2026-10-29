import { screen } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";
import { axe } from "vitest-axe";
import { fr } from "@/i18n/fr";
import { API_URL, server } from "@/test/msw";
import { aDisponible, aDocument, MISSION_ID, OBJET_ID, renderDocuments } from "../testUtils";
import { DocumentInline } from "./DocumentInline";

const d = fr.documents;

describe("DocumentInline", () => {
  it("shows number, version, status and both actions for a generated document", async () => {
    server.use(
      http.get(`${API_URL}/api/v1/documents/available/`, ({ request }) => {
        expect(new URL(request.url).searchParams.get("mission")).toBe(MISSION_ID);
        return HttpResponse.json([
          aDisponible({ document: aDocument() }),
          aDisponible({ type_document: "AUTRE", libelle: "Autre", objet_id: "x" }),
        ]);
      }),
    );
    const { container } = renderDocuments(
      <DocumentInline typeDocument="ORDRE_MISSION" objetId={OBJET_ID} missionId={MISSION_ID} />,
    );
    expect(await screen.findByText("OM-2026-001")).toBeInTheDocument();
    expect(screen.getByText("Ordre de mission")).toBeInTheDocument();
    expect(screen.getByText("v1")).toBeInTheDocument();
    expect(screen.getByText("Prête")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: d.regenerate })).toBeEnabled();
    expect(screen.getByRole("button", { name: d.downloadWord })).toBeEnabled();
    expect(screen.queryByText("Autre")).not.toBeInTheDocument();
    expect(
      (await axe(container, { rules: { "color-contrast": { enabled: false } } })).violations,
    ).toEqual([]);
  });

  it("offers « Générer » and no download when nothing was generated yet", async () => {
    server.use(
      http.get(`${API_URL}/api/v1/documents/available/`, () => HttpResponse.json([aDisponible()])),
    );
    renderDocuments(
      <DocumentInline typeDocument="ORDRE_MISSION" objetId={OBJET_ID} missionId={MISSION_ID} />,
    );
    expect(await screen.findByRole("button", { name: d.generate })).toBeEnabled();
    expect(screen.queryByRole("button", { name: d.downloadWord })).not.toBeInTheDocument();
  });
});
