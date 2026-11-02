import { describe, expect, it } from "vitest";
import { ApiError } from "./errors";
import { shouldRetry } from "./queryClient";

describe("shouldRetry", () => {
  it("ne réessaie jamais une erreur client (404, 403, 422…) : l'écran doit répondre tout de suite", () => {
    for (const status of [400, 401, 403, 404, 422]) {
      expect(shouldRetry(0, new ApiError(status, "x"))).toBe(false);
    }
  });

  it("réessaie deux fois au plus une panne réseau ou une erreur serveur", () => {
    expect(shouldRetry(0, new ApiError(0, "réseau"))).toBe(true);
    expect(shouldRetry(1, new ApiError(503, "indisponible"))).toBe(true);
    expect(shouldRetry(2, new ApiError(503, "indisponible"))).toBe(false);
  });
});
