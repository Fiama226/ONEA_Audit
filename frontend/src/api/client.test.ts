import { http, HttpResponse } from "msw";
import { afterEach, describe, expect, it } from "vitest";
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
});
