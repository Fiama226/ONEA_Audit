import { http, HttpResponse } from "msw";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { fr } from "@/i18n/fr";
import { API_URL, server } from "@/test/msw";
import { setTokenProvider } from "./client";
import { isApiError } from "./errors";
import { uploadWithProgress } from "./upload";

const CORS = { "Access-Control-Allow-Origin": "*" };

afterEach(() => setTokenProvider(() => null));

// jsdom envoie une pré-requête CORS dès qu'un écouteur de progression est posé.
beforeEach(() =>
  server.use(
    http.options(
      `${API_URL}/api/v1/evidence/`,
      () =>
        new HttpResponse(null, {
          status: 204,
          headers: {
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "*",
            "Access-Control-Allow-Methods": "POST",
          },
        }),
    ),
  ),
);

function form(): FormData {
  const data = new FormData();
  data.append("fichier", new File(["abc"], "preuve.pdf", { type: "application/pdf" }));
  return data;
}

describe("uploadWithProgress", () => {
  it("résout avec le JSON, envoie le jeton et termine la progression à 1", async () => {
    let auth: string | null = null;
    server.use(
      http.post(`${API_URL}/api/v1/evidence/`, ({ request }) => {
        auth = request.headers.get("Authorization");
        return HttpResponse.json({ id: "p1" }, { status: 201, headers: CORS });
      }),
    );
    setTokenProvider(() => "tok");
    const ratios: number[] = [];
    const result = await uploadWithProgress<{ id: string }>("/api/v1/evidence/", form(), (r) =>
      ratios.push(r),
    );
    expect(result.id).toBe("p1");
    expect(auth).toBe("Bearer tok");
    expect(ratios.at(-1)).toBe(1);
  });

  it("transmet la progression d'envoi (0 à 1)", async () => {
    class FakeXhr {
      upload: { onprogress: ((e: ProgressEvent) => void) | null } = { onprogress: null };
      status = 201;
      responseText = "{}";
      onload: (() => void) | null = null;
      onerror: (() => void) | null = null;
      onabort: (() => void) | null = null;
      open = vi.fn();
      setRequestHeader = vi.fn();
      abort = vi.fn();
      send = () => {
        this.upload.onprogress?.({ lengthComputable: true, loaded: 1, total: 4 } as ProgressEvent);
        this.upload.onprogress?.({ lengthComputable: true, loaded: 4, total: 4 } as ProgressEvent);
        this.onload?.();
      };
    }
    vi.stubGlobal("XMLHttpRequest", FakeXhr);
    const ratios: number[] = [];
    await uploadWithProgress("/api/v1/evidence/", form(), (r) => ratios.push(r));
    vi.unstubAllGlobals();
    expect(ratios).toEqual([0.25, 1, 1]);
  });

  it("400 : erreurs par champ au format {detail, errors}", async () => {
    server.use(
      http.post(`${API_URL}/api/v1/evidence/`, () =>
        HttpResponse.json(
          { detail: "Données invalides.", errors: { libelle: ["Ce champ est obligatoire."] } },
          { status: 400, headers: CORS },
        ),
      ),
    );
    const error = await uploadWithProgress("/api/v1/evidence/", form(), () => {}).catch(
      (e: unknown) => e,
    );
    expect(isApiError(error) && error.status).toBe(400);
    expect(isApiError(error) && error.errors.libelle).toEqual(["Ce champ est obligatoire."]);
  });

  it("413 (Nginx, corps HTML) : message de taille maximale", async () => {
    server.use(
      http.post(
        `${API_URL}/api/v1/evidence/`,
        () => new HttpResponse("<html>413</html>", { status: 413, headers: CORS }),
      ),
    );
    const error = await uploadWithProgress("/api/v1/evidence/", form(), () => {}).catch(
      (e: unknown) => e,
    );
    expect(isApiError(error) && error.detail).toBe(fr.errors.fileTooLarge);
  });

  it("annulation : AbortError", async () => {
    server.use(
      http.post(`${API_URL}/api/v1/evidence/`, async () => {
        await new Promise((resolve) => setTimeout(resolve, 200));
        return HttpResponse.json({}, { headers: CORS });
      }),
    );
    const controller = new AbortController();
    const promise = uploadWithProgress("/api/v1/evidence/", form(), () => {}, controller.signal);
    controller.abort();
    await expect(promise).rejects.toMatchObject({ name: "AbortError" });
  });
});
