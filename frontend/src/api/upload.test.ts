import { http, HttpResponse } from "msw";
import { beforeEach, describe, expect, it, onTestFinished, vi } from "vitest";
import { fr } from "@/i18n/fr";
import { API_URL, server, TEST_CSRF } from "@/test/msw";
import {
  ensureCsrfToken,
  resetCsrfToken,
  setSessionUser,
  setUnauthorizedHandler,
} from "./client";
import { isApiError } from "./errors";
import { uploadWithProgress } from "./upload";

// Requête avec cookie de session (withCredentials) : origine exacte et autorisation explicite.
const CORS = {
  "Access-Control-Allow-Origin": window.location.origin,
  "Access-Control-Allow-Credentials": "true",
};

beforeEach(() => resetCsrfToken());

// jsdom envoie une pré-requête CORS dès qu'un écouteur de progression est posé.
beforeEach(() =>
  server.use(
    http.options(
      `${API_URL}/api/v1/evidence/`,
      () =>
        new HttpResponse(null, {
          status: 204,
          headers: {
            ...CORS,
            "Access-Control-Allow-Headers": "Accept, X-CSRFToken",
            "Access-Control-Allow-Methods": "POST",
          },
        }),
    ),
  ),
);

const REFUS_CSRF = { detail: "Jeton CSRF absent ou invalide : rechargez la page.", errors: {} };

function form(): FormData {
  const data = new FormData();
  data.append("fichier", new File(["abc"], "preuve.pdf", { type: "application/pdf" }));
  return data;
}

describe("uploadWithProgress", () => {
  it("résout avec le JSON, envoie le jeton CSRF et termine la progression à 1", async () => {
    let csrf: string | null = null;
    let authorization: string | null = "unset";
    server.use(
      http.post(`${API_URL}/api/v1/evidence/`, ({ request }) => {
        csrf = request.headers.get("X-CSRFToken");
        authorization = request.headers.get("Authorization");
        return HttpResponse.json({ id: "p1" }, { status: 201, headers: CORS });
      }),
    );
    const ratios: number[] = [];
    const result = await uploadWithProgress<{ id: string }>("/api/v1/evidence/", form(), (r) =>
      ratios.push(r),
    );
    expect(result.id).toBe("p1");
    expect(csrf).toBe(TEST_CSRF);
    expect(authorization).toBeNull();
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

  it("401 (session expirée pendant l'envoi) : gestionnaire de session appelé, message dédié", async () => {
    let expirees = 0;
    setUnauthorizedHandler(() => {
      expirees += 1;
    });
    onTestFinished(() => setUnauthorizedHandler(null));
    server.use(
      http.post(
        `${API_URL}/api/v1/evidence/`,
        () => new HttpResponse("<html>401</html>", { status: 401, headers: CORS }),
      ),
    );
    const error = await uploadWithProgress("/api/v1/evidence/", form(), () => {}).catch(
      (e: unknown) => e,
    );
    expect(isApiError(error) && error.status).toBe(401);
    expect(isApiError(error) && error.detail).toBe(fr.errors.unauthorized);
    expect(expirees).toBe(1);
  });

  it("jeton CSRF périmé : jeton oublié, redemandé, envoi rejoué une seule fois", async () => {
    let emis = 0;
    const recus: (string | null)[] = [];
    server.use(
      http.get(`${API_URL}/api/v1/auth/csrf/`, () => {
        emis += 1;
        return HttpResponse.json({ csrf_token: `jeton-${emis}` });
      }),
      http.post(`${API_URL}/api/v1/evidence/`, ({ request }) => {
        const jeton = request.headers.get("X-CSRFToken");
        recus.push(jeton);
        return jeton === "jeton-1"
          ? HttpResponse.json(REFUS_CSRF, { status: 403, headers: CORS })
          : HttpResponse.json({ id: "p2" }, { status: 201, headers: CORS });
      }),
    );
    const result = await uploadWithProgress<{ id: string }>("/api/v1/evidence/", form(), () => {});
    expect(result.id).toBe("p2");
    expect(recus).toEqual(["jeton-1", "jeton-2"]);
    // Le jeton neuf est gardé pour les écritures suivantes.
    expect(await ensureCsrfToken()).toBe("jeton-2");
  });

  it("second refus CSRF : erreur remontée sans boucle", async () => {
    let envois = 0;
    server.use(
      http.post(`${API_URL}/api/v1/evidence/`, () => {
        envois += 1;
        return HttpResponse.json(REFUS_CSRF, { status: 403, headers: CORS });
      }),
    );
    const error = await uploadWithProgress("/api/v1/evidence/", form(), () => {}).catch(
      (e: unknown) => e,
    );
    expect(isApiError(error) && error.status).toBe(403);
    expect(envois).toBe(2);
  });

  it("refus CSRF après connexion d'un autre agent : pas de rejeu", async () => {
    let envois = 0;
    setSessionUser(7);
    onTestFinished(() => setSessionUser(null));
    server.use(
      http.get(`${API_URL}/api/v1/auth/session/`, () =>
        HttpResponse.json({ etape: "OK", me: { id: 9 } }),
      ),
      http.post(`${API_URL}/api/v1/evidence/`, () => {
        envois += 1;
        return HttpResponse.json(REFUS_CSRF, { status: 403, headers: CORS });
      }),
    );
    const error = await uploadWithProgress("/api/v1/evidence/", form(), () => {}).catch(
      (e: unknown) => e,
    );
    expect(isApiError(error) && error.detail).toBe(fr.auth.sessionChanged);
    expect(envois).toBe(1);
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
