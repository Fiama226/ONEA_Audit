import { http, HttpResponse } from "msw";
import { afterEach, describe, expect, it, vi } from "vitest";
import { fr } from "@/i18n/fr";
import { API_URL, server } from "@/test/msw";
import { downloadEvidence } from "./download";
import { isApiError } from "./errors";

afterEach(() => vi.restoreAllMocks());

describe("downloadEvidence", () => {
  it("télécharge via un lien temporaire portant le nom demandé", async () => {
    server.use(
      http.get(`${API_URL}/api/v1/evidence/p1/download/`, () => new HttpResponse("contenu")),
    );
    URL.createObjectURL = vi.fn(() => "blob:test");
    URL.revokeObjectURL = vi.fn();
    const click = vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => {});
    await downloadEvidence("p1", "preuve.pdf");
    expect(click).toHaveBeenCalledTimes(1);
    await vi.waitFor(() => expect(URL.revokeObjectURL).toHaveBeenCalledWith("blob:test"));
    expect(document.querySelector("a[download]")).toBeNull();
  });

  it("409 : message d'intégrité", async () => {
    server.use(
      http.get(`${API_URL}/api/v1/evidence/p1/download/`, () =>
        HttpResponse.json({ detail: "x" }, { status: 409 }),
      ),
    );
    const error = await downloadEvidence("p1", "preuve.pdf").catch((e: unknown) => e);
    expect(isApiError(error) && error.status).toBe(409);
    expect(isApiError(error) && error.detail).toBe(fr.errors.evidenceIntegrity);
  });
});
