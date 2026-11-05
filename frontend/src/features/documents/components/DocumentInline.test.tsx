import { screen } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";
import { axe } from "vitest-axe";
import { fr } from "@/i18n/fr";
import { API_URL, server } from "@/test/msw";
import { aDisponible, aDocument, MISSION_ID, OBJET_ID, renderDocuments } from "../testUtils";
import { DocumentInline, MissionDocuments } from "./DocumentInline";

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

  it("shows a loading status, then an explicit empty state when the item is unknown", async () => {
    server.use(http.get(`${API_URL}/api/v1/documents/available/`, () => HttpResponse.json([])));
    renderDocuments(
      <DocumentInline typeDocument="ORDRE_MISSION" objetId={OBJET_ID} missionId={MISSION_ID} />,
    );
    expect(screen.getByRole("status")).toHaveTextContent(fr.common.loading);
    expect(await screen.findByText(d.noDocument)).toBeInTheDocument();
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

  it("hides « Générer » when the user may not generate, and shows the reason", async () => {
    server.use(
      http.get(`${API_URL}/api/v1/documents/available/`, () =>
        HttpResponse.json([
          aDisponible({
            peut_generer: false,
            raison: "Vous n'avez pas le droit de générer ce document.",
          }),
        ]),
      ),
    );
    renderDocuments(
      <DocumentInline typeDocument="ORDRE_MISSION" objetId={OBJET_ID} missionId={MISSION_ID} />,
    );
    expect(
      await screen.findByText("Vous n'avez pas le droit de générer ce document."),
    ).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: d.generate })).not.toBeInTheDocument();
  });

  it("lists every available document of the mission in the side panel", async () => {
    server.use(
      http.get(`${API_URL}/api/v1/documents/available/`, () =>
        HttpResponse.json([
          aDisponible(),
          aDisponible({ type_document: "PV_OUVERTURE", libelle: "PV d'ouverture", objet_id: "x" }),
        ]),
      ),
    );
    renderDocuments(<MissionDocuments missionId={MISSION_ID} />);
    expect(await screen.findByText("Ordre de mission")).toBeInTheDocument();
    expect(screen.getByText("PV d'ouverture")).toBeInTheDocument();
    expect(screen.getAllByRole("button", { name: d.generate })).toHaveLength(2);
  });
});
