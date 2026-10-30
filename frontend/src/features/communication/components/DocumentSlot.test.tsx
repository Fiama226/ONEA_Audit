import { screen } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";
import { aDisponible, aDocument, renderDocuments } from "@/features/documents/testUtils";
import { API_URL, server } from "@/test/msw";
import { MISSION_ID, RAPPORT_ID } from "../testUtils";
import { DocumentSlot } from "./DocumentSlot";

describe("DocumentSlot", () => {
  it("monte le document du lot 4 pour l'objet demandé", async () => {
    server.use(
      http.get(`${API_URL}/api/v1/documents/available/`, () =>
        HttpResponse.json([
          aDisponible({
            type_document: "VALIDATION_RAPPORT",
            libelle: "Rapport d'audit",
            objet_id: RAPPORT_ID,
            document: aDocument(),
          }),
        ]),
      ),
    );
    renderDocuments(
      <DocumentSlot
        typeDocument="VALIDATION_RAPPORT"
        objetId={RAPPORT_ID}
        missionId={MISSION_ID}
      />,
    );
    expect(await screen.findByText("Rapport d'audit")).toBeInTheDocument();
    expect(screen.getByText("OM-2026-001")).toBeInTheDocument();
  });
});
