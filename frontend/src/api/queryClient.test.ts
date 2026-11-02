import { describe, expect, it } from "vitest";
import { ApiError } from "./errors";
import { shouldRetry } from "./queryClient";

describe("shouldRetry", () => {
  it("ne rejoue jamais une réponse 4xx (404, 403, 422) : l'erreur s'affiche tout de suite", () => {
    for (const status of [400, 403, 404, 422]) {
      expect(shouldRetry(0, new ApiError(status, "x"))).toBe(false);
    }
  });
  it("rejoue une fois une panne réseau ou une erreur serveur", () => {
    expect(shouldRetry(0, new ApiError(503, "x"))).toBe(true);
    expect(shouldRetry(0, new TypeError("Failed to fetch"))).toBe(true);
    expect(shouldRetry(1, new ApiError(503, "x"))).toBe(false);
  });
});
