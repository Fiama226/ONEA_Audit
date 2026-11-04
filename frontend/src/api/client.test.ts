import { http, HttpResponse } from "msw";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { fr } from "@/i18n/fr";
import { API_URL, server, TEST_CSRF } from "@/test/msw";
import {
  apiDownload,
  apiFetch,
  apiUpload,
  ensureCsrfToken,
  resetCsrfToken,
  setUnauthorizedHandler,
} from "./client";
import { ApiError, isApiError } from "./errors";

describe("apiDownload filename sanitising", () => {
  it("strips path segments and control characters", async () => {
    server.use(
      http.get(
        `${API_URL}/api/v1/evil/`,
        () =>
          new HttpResponse("x", {
            headers: {
              "Content-Disposition": "attachment; filename*=UTF-8''..%2F..%5Cetc%2Fpasswd%0A.docx",
            },
          }),
      ),
    );
    const { filename } = await apiDownload("/api/v1/evil/");
    expect(filename).toBe("passwd.docx");
  });
});

describe("apiUpload", () => {
  it("sends FormData with a multipart boundary (no forced JSON type) and the CSRF token", async () => {
    let contentType: string | null = null;
    let csrf: string | null = null;
    let file: FormDataEntryValue | null = null;
    server.use(
      http.post(`${API_URL}/api/v1/up/`, async ({ request }) => {
        contentType = request.headers.get("Content-Type");
        csrf = request.headers.get("X-CSRFToken");
        file = (await request.formData()).get("fichier");
        return HttpResponse.json({ id: "1" }, { status: 201 });
      }),
    );
    const body = new FormData();
    body.append("fichier", new File(["x"], "g.docx"));
    await expect(apiUpload("/api/v1/up/", body)).resolves.toEqual({ id: "1" });
    expect(contentType).toMatch(/^multipart\/form-data; boundary=/);
    expect(csrf).toBe(TEST_CSRF);
    expect(file).not.toBeNull();
  });

  it("rejects with an AbortError (not a network ApiError) when the signal aborts", async () => {
    server.use(
      http.post(`${API_URL}/api/v1/up/`, async () => {
        await new Promise((r) => setTimeout(r, 500));
        return HttpResponse.json({ id: "1" }, { status: 201 });
      }),
    );
    const controller = new AbortController();
    const pending = apiUpload("/api/v1/up/", new FormData(), controller.signal).catch(
      (e: unknown) => e,
    );
    controller.abort();
    const err = await pending;
    expect(isApiError(err)).toBe(false);
    expect((err as DOMException).name).toBe("AbortError");
  });

  it("turns a 422 into an ApiError with errors.fichier", async () => {
    server.use(
      http.post(`${API_URL}/api/v1/up/`, () =>
        HttpResponse.json(
          { detail: "Invalide", errors: { fichier: ["Balise manquante."] } },
          { status: 422 },
        ),
      ),
    );
    const err = await apiUpload("/api/v1/up/", new FormData()).catch((e: unknown) => e);
    expect(isApiError(err)).toBe(true);
    expect((err as ApiError).status).toBe(422);
    expect((err as ApiError).errors.fichier).toEqual(["Balise manquante."]);
  });
});

beforeEach(() => resetCsrfToken());

/** `credentials` passé à fetch pour l'URL donnée (MSW ne le transmet pas au handler). */
function credentialsOf(spy: { mock: { calls: unknown[][] } }, suffix: string) {
  const call = spy.mock.calls.find(([url]) => String(url).endsWith(suffix));
  return (call?.[1] as RequestInit | undefined)?.credentials;
}

describe("apiDownload", () => {
  it("prefers filename*=UTF-8'' and sends the session cookie", async () => {
    const spy = vi.spyOn(globalThis, "fetch");
    server.use(
      http.get(`${API_URL}/api/v1/x/`, () => {
        return new HttpResponse("a;b", {
          headers: {
            "Content-Disposition":
              "attachment; filename=\"fallback.csv\"; filename*=UTF-8''cartographie-2026.csv",
          },
        });
      }),
    );
    const { blob, filename } = await apiDownload("/api/v1/x/");
    expect(filename).toBe("cartographie-2026.csv");
    expect(credentialsOf(spy, "/api/v1/x/")).toBe("include");
    spy.mockRestore();
    expect(await blob.text()).toBe("a;b");
  });

  it("falls back to the quoted filename, then to a default", async () => {
    server.use(
      http.get(
        `${API_URL}/api/v1/q/`,
        () =>
          new HttpResponse("x", {
            headers: { "Content-Disposition": 'attachment; filename="a b.xlsx"' },
          }),
      ),
      http.get(`${API_URL}/api/v1/n/`, () => new HttpResponse("x")),
    );
    expect((await apiDownload("/api/v1/q/")).filename).toBe("a b.xlsx");
    expect((await apiDownload("/api/v1/n/")).filename).toBe("export");
  });

  it("shows the server 429 message, with a French fallback when the body is not JSON", async () => {
    server.use(
      http.get(`${API_URL}/api/v1/t1/`, () =>
        HttpResponse.json(
          { detail: "Trop de requêtes : réessayez dans 42 secondes.", errors: {} },
          { status: 429, headers: { "Retry-After": "42" } },
        ),
      ),
      http.get(`${API_URL}/api/v1/t2/`, () => new HttpResponse("<html>", { status: 429 })),
    );
    const e1 = await apiDownload("/api/v1/t1/").catch((e: unknown) => e);
    expect((e1 as ApiError).status).toBe(429);
    expect((e1 as ApiError).detail).toBe("Trop de requêtes : réessayez dans 42 secondes.");
    const e2 = await apiDownload("/api/v1/t2/").catch((e: unknown) => e);
    expect((e2 as ApiError).detail).toBe(fr.errors.tooManyRequests);
  });

  it("throws ApiError on 403", async () => {
    server.use(http.get(`${API_URL}/api/v1/f/`, () => new HttpResponse(null, { status: 403 })));
    const error = await apiDownload("/api/v1/f/").catch((e: unknown) => e);
    expect(isApiError(error)).toBe(true);
    expect((error as ApiError).status).toBe(403);
    expect((error as ApiError).detail).toBe(fr.errors.forbidden);
  });
});

describe("apiFetch", () => {
  it("returns the parsed JSON body", async () => {
    server.use(http.get(`${API_URL}/api/missions/`, () => HttpResponse.json({ count: 2 })));
    await expect(apiFetch<{ count: number }>("/api/missions/")).resolves.toEqual({ count: 2 });
  });

  it("turns a 422 response into an ApiError carrying field errors", async () => {
    server.use(
      http.post(`${API_URL}/api/missions/`, () =>
        HttpResponse.json(
          { detail: "Données invalides", errors: { titre: ["Ce champ est obligatoire."] } },
          { status: 422 },
        ),
      ),
    );
    const error = await apiFetch("/api/missions/", { method: "POST", json: {} }).catch(
      (e: unknown) => e,
    );
    expect(isApiError(error)).toBe(true);
    expect(error).toBeInstanceOf(ApiError);
    const apiError = error as ApiError;
    expect(apiError.status).toBe(422);
    expect(apiError.detail).toBe("Données invalides");
    expect(apiError.errors).toEqual({ titre: ["Ce champ est obligatoire."] });
  });

  it("sends the session cookie and never an Authorization header", async () => {
    const spy = vi.spyOn(globalThis, "fetch");
    let authorization: string | null = "unset";
    server.use(
      http.get(`${API_URL}/api/me/`, ({ request }) => {
        authorization = request.headers.get("Authorization");
        return HttpResponse.json({});
      }),
    );
    await apiFetch("/api/me/");
    expect(credentialsOf(spy, "/api/me/")).toBe("include");
    spy.mockRestore();
    expect(authorization).toBeNull();
  });

  it("sends a JSON body with content type when json is provided", async () => {
    let body: unknown = null;
    let contentType: string | null = null;
    server.use(
      http.post(`${API_URL}/api/x/`, async ({ request }) => {
        contentType = request.headers.get("Content-Type");
        body = await request.json();
        return HttpResponse.json({ ok: true });
      }),
    );
    await apiFetch("/api/x/", { method: "POST", json: { a: 1 } });
    expect(body).toEqual({ a: 1 });
    expect(contentType).toBe("application/json");
  });

  it("returns undefined on 204", async () => {
    server.use(http.delete(`${API_URL}/api/x/1/`, () => new HttpResponse(null, { status: 204 })));
    await expect(apiFetch("/api/x/1/", { method: "DELETE" })).resolves.toBeUndefined();
  });

  it("throws ApiError status 0 with the network message when fetch rejects", async () => {
    server.use(http.get(`${API_URL}/api/net/`, () => HttpResponse.error()));
    const error = await apiFetch("/api/net/").catch((e: unknown) => e);
    expect(isApiError(error)).toBe(true);
    expect((error as ApiError).status).toBe(0);
    expect((error as ApiError).detail).toBe(fr.errors.network);
  });

  it.each([
    [401, fr.errors.unauthorized],
    [403, fr.errors.forbidden],
    [404, fr.errors.notFound],
  ])("maps an empty %i response to its French message", async (status, message) => {
    server.use(http.get(`${API_URL}/api/s/`, () => new HttpResponse(null, { status })));
    const error = await apiFetch("/api/s/").catch((e: unknown) => e);
    expect((error as ApiError).status).toBe(status);
    expect((error as ApiError).detail).toBe(message);
  });

  it("maps a non-JSON error body to the status message", async () => {
    server.use(
      http.get(
        `${API_URL}/api/s/`,
        () => new HttpResponse("<html>Forbidden</html>", { status: 403 }),
      ),
    );
    const error = await apiFetch("/api/s/").catch((e: unknown) => e);
    expect((error as ApiError).detail).toBe(fr.errors.forbidden);
  });

  it("throws a generic ApiError when a 2xx body is not JSON", async () => {
    server.use(
      http.get(`${API_URL}/api/html/`, () => new HttpResponse("<html></html>", { status: 200 })),
    );
    const error = await apiFetch("/api/html/").catch((e: unknown) => e);
    expect(isApiError(error)).toBe(true);
    expect((error as ApiError).detail).toBe(fr.errors.generic);
  });
});

describe("session expirée en cours d'utilisation (401)", () => {
  afterEach(() => setUnauthorizedHandler(null));

  it("signale le 401 d'une requête métier au gestionnaire de session", async () => {
    let calls = 0;
    setUnauthorizedHandler(() => {
      calls += 1;
    });
    server.use(
      http.get(`${API_URL}/api/v1/ressource/`, () =>
        HttpResponse.json({ detail: "Session expirée.", errors: {} }, { status: 401 }),
      ),
    );
    await expect(apiFetch("/api/v1/ressource/")).rejects.toMatchObject({ status: 401 });
    expect(calls).toBe(1);
  });

  it.each([
    ["GET", "/api/v1/auth/session/"],
    ["POST", "/api/v1/auth/login/"],
    ["POST", "/api/v1/auth/login/otp/"],
    ["POST", "/api/v1/auth/logout/"],
    ["POST", "/api/v1/auth/password/forgot/"],
    ["POST", "/api/v1/auth/password/reset/"],
  ])("ne le déclenche pas pour %s %s (anonyme ou échec de connexion)", async (method, path) => {
    let calls = 0;
    setUnauthorizedHandler(() => {
      calls += 1;
    });
    const reply = () => HttpResponse.json({ detail: "x", errors: {} }, { status: 401 });
    server.use(
      method === "GET"
        ? http.get(`${API_URL}${path}`, reply)
        : http.post(`${API_URL}${path}`, reply),
    );
    await expect(apiFetch(path, { method })).rejects.toBeInstanceOf(ApiError);
    expect(calls).toBe(0);
  });

  it("le déclenche pour le changement de mot de passe (session requise)", async () => {
    let calls = 0;
    setUnauthorizedHandler(() => {
      calls += 1;
    });
    server.use(
      http.post(`${API_URL}/api/v1/auth/password/change/`, () =>
        HttpResponse.json({ detail: "x", errors: {} }, { status: 401 }),
      ),
    );
    await expect(
      apiFetch("/api/v1/auth/password/change/", { method: "POST", json: {} }),
    ).rejects.toBeInstanceOf(ApiError);
    expect(calls).toBe(1);
  });

  it("ne le déclenche pas pour un 403", async () => {
    let calls = 0;
    setUnauthorizedHandler(() => {
      calls += 1;
    });
    server.use(
      http.get(`${API_URL}/api/v1/interdit/`, () =>
        HttpResponse.json({ detail: "x", errors: {} }, { status: 403 }),
      ),
    );
    await expect(apiFetch("/api/v1/interdit/")).rejects.toBeInstanceOf(ApiError);
    expect(calls).toBe(0);
  });
});

describe("jeton CSRF", () => {
  const REFUS_CSRF = { detail: "Jeton CSRF absent ou invalide : rechargez la page.", errors: {} };

  it("jeton périmé : 403 CSRF, nouveau jeton puis un seul rejeu réussi", async () => {
    let emis = 0;
    const recus: (string | null)[] = [];
    server.use(
      http.get(`${API_URL}/api/v1/auth/csrf/`, () => {
        emis += 1;
        return HttpResponse.json({ csrf_token: `jeton-${emis}` });
      }),
      http.post(`${API_URL}/api/x/`, ({ request }) => {
        const jeton = request.headers.get("X-CSRFToken");
        recus.push(jeton);
        return jeton === "jeton-1"
          ? HttpResponse.json(REFUS_CSRF, { status: 403 })
          : HttpResponse.json({ ok: true });
      }),
    );
    await expect(apiFetch("/api/x/", { method: "POST", json: { a: 1 } })).resolves.toEqual({
      ok: true,
    });
    expect(recus).toEqual(["jeton-1", "jeton-2"]);
    expect(emis).toBe(2);
  });

  it("second 403 CSRF : erreur remontée, sans boucle", async () => {
    let emis = 0;
    let envois = 0;
    server.use(
      http.get(`${API_URL}/api/v1/auth/csrf/`, () => {
        emis += 1;
        return HttpResponse.json({ csrf_token: `jeton-${emis}` });
      }),
      http.post(`${API_URL}/api/x/`, () => {
        envois += 1;
        return HttpResponse.json(REFUS_CSRF, { status: 403 });
      }),
    );
    const error = await apiFetch("/api/x/", { method: "POST", json: {} }).catch((e: unknown) => e);
    expect(isApiError(error) && error.status).toBe(403);
    expect(isApiError(error) && error.detail).toBe(REFUS_CSRF.detail);
    expect(envois).toBe(2);
    expect(emis).toBe(2);
  });

  it("un 403 de droits (pas CSRF) n'est pas rejoué", async () => {
    let envois = 0;
    server.use(
      http.post(`${API_URL}/api/x/`, () => {
        envois += 1;
        return HttpResponse.json({ detail: "Accès refusé.", errors: {} }, { status: 403 });
      }),
    );
    await expect(apiFetch("/api/x/", { method: "POST", json: {} })).rejects.toMatchObject({
      status: 403,
    });
    expect(envois).toBe(1);
  });

  it("reset pendant une demande de jeton : le jeton reçu n'est pas mémorisé", async () => {
    let emis = 0;
    let liberer: () => void = () => {};
    const premier = new Promise<void>((resolve) => {
      liberer = resolve;
    });
    server.use(
      http.get(`${API_URL}/api/v1/auth/csrf/`, async () => {
        emis += 1;
        const numero = emis;
        if (numero === 1) await premier;
        return HttpResponse.json({ csrf_token: `jeton-${numero}` });
      }),
    );
    const enCours = ensureCsrfToken();
    resetCsrfToken();
    liberer();
    expect(await enCours).toBe("jeton-1");
    expect(await ensureCsrfToken()).toBe("jeton-2");
    expect(await ensureCsrfToken()).toBe("jeton-2");
    expect(emis).toBe(2);
  });

  it("joint X-CSRFToken aux écritures, pas aux lectures, et le met en cache", async () => {
    let emis = 0;
    const spy = vi.spyOn(globalThis, "fetch");
    const recus: (string | null)[] = [];
    server.use(
      http.get(`${API_URL}/api/v1/auth/csrf/`, () => {
        emis += 1;
        return HttpResponse.json({ csrf_token: `jeton-${emis}` });
      }),
      http.get(`${API_URL}/api/x/`, ({ request }) => {
        recus.push(request.headers.get("X-CSRFToken"));
        return HttpResponse.json({});
      }),
      http.post(`${API_URL}/api/x/`, ({ request }) => {
        recus.push(request.headers.get("X-CSRFToken"));
        return HttpResponse.json({});
      }),
      http.delete(`${API_URL}/api/x/`, ({ request }) => {
        recus.push(request.headers.get("X-CSRFToken"));
        return new HttpResponse(null, { status: 204 });
      }),
    );
    await apiFetch("/api/x/");
    await apiFetch("/api/x/", { method: "POST", json: {} });
    await apiFetch("/api/x/", { method: "DELETE" });
    expect(recus).toEqual([null, "jeton-1", "jeton-1"]);
    expect(emis).toBe(1);
    expect(credentialsOf(spy, "/api/v1/auth/csrf/")).toBe("include");
    spy.mockRestore();
  });

  it("redemande le jeton après resetCsrfToken (rotation à la connexion)", async () => {
    let emis = 0;
    server.use(
      http.get(`${API_URL}/api/v1/auth/csrf/`, () => {
        emis += 1;
        return HttpResponse.json({ csrf_token: `jeton-${emis}` });
      }),
    );
    expect(await ensureCsrfToken()).toBe("jeton-1");
    expect(await ensureCsrfToken()).toBe("jeton-1");
    resetCsrfToken();
    expect(await ensureCsrfToken()).toBe("jeton-2");
  });

  it("partage une seule demande entre écritures simultanées", async () => {
    let emis = 0;
    server.use(
      http.get(`${API_URL}/api/v1/auth/csrf/`, () => {
        emis += 1;
        return HttpResponse.json({ csrf_token: "jeton" });
      }),
    );
    await Promise.all([ensureCsrfToken(), ensureCsrfToken(), ensureCsrfToken()]);
    expect(emis).toBe(1);
  });

  it("échec de la demande de jeton : ApiError réseau, sans envoyer l'écriture", async () => {
    let ecritures = 0;
    server.use(
      http.get(`${API_URL}/api/v1/auth/csrf/`, () => HttpResponse.error()),
      http.post(`${API_URL}/api/x/`, () => {
        ecritures += 1;
        return HttpResponse.json({});
      }),
    );
    const error = await apiFetch("/api/x/", { method: "POST", json: {} }).catch((e: unknown) => e);
    expect(isApiError(error) && error.status).toBe(0);
    expect(ecritures).toBe(0);
  });
});
