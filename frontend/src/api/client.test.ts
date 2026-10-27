import { http, HttpResponse } from "msw";
import { afterEach, describe, expect, it } from "vitest";
import { fr } from "@/i18n/fr";
import { API_URL, server } from "@/test/msw";
import { apiFetch, setTokenProvider } from "./client";
import { ApiError, isApiError } from "./errors";

afterEach(() => setTokenProvider(() => null));

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

  it("adds the Authorization header from the token provider", async () => {
    let received: string | null = null;
    server.use(
      http.get(`${API_URL}/api/me/`, ({ request }) => {
        received = request.headers.get("Authorization");
        return HttpResponse.json({});
      }),
    );
    setTokenProvider(() => "abc123");
    await apiFetch("/api/me/");
    expect(received).toBe("Bearer abc123");
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

  it("sends no Authorization header without a token", async () => {
    let received: string | null = "unset";
    server.use(
      http.get(`${API_URL}/api/me/`, ({ request }) => {
        received = request.headers.get("Authorization");
        return HttpResponse.json({});
      }),
    );
    await apiFetch("/api/me/");
    expect(received).toBeNull();
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
