import { http, HttpResponse } from "msw";
import { describe, expect, it, vi } from "vitest";
import { fr } from "@/i18n/fr";
import { API_URL, server } from "@/test/msw";
import { downloadReport } from "./api";
import { RAPPORT_ID } from "./testUtils";

vi.mock("@/lib/download", () => ({ downloadBlob: vi.fn() }));

describe("downloadReport", () => {
  it("transforme un 409 en message d'intégrité", async () => {
    server.use(
      http.get(`${API_URL}/api/v1/reports/${RAPPORT_ID}/download/`, () =>
        HttpResponse.json({ detail: "x" }, { status: 409 }),
      ),
    );
    await expect(downloadReport(RAPPORT_ID, "pdf", "rapport")).rejects.toThrow(
      fr.documents.integrityError,
    );
  });

  it("transmet le format et le document demandés", async () => {
    let url: URL | undefined;
    server.use(
      http.get(`${API_URL}/api/v1/reports/${RAPPORT_ID}/download/`, ({ request }) => {
        url = new URL(request.url);
        return new HttpResponse("contenu", {
          headers: { "Content-Disposition": 'attachment; filename="rapport.docx"' },
        });
      }),
    );
    await downloadReport(RAPPORT_ID, "docx", "note");
    expect(url?.searchParams.get("format")).toBe("docx");
    expect(url?.searchParams.get("document")).toBe("note");
  });
});
