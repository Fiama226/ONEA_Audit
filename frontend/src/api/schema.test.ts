import { describe, expectTypeOf, it } from "vitest";

import type { components, paths } from "./schema";

type Me = components["schemas"]["Me"];
type ApiErrorBody = components["schemas"]["ApiError"];

// Type-level contract tests: a backend drift regenerates schema.d.ts and breaks `tsc`.
describe("generated OpenAPI types", () => {
  it("exposes the Me component with the expected fields", () => {
    expectTypeOf<Me>().toHaveProperty("id").toEqualTypeOf<number>();
    expectTypeOf<Me>().toHaveProperty("username").toEqualTypeOf<string>();
    expectTypeOf<Me>().toHaveProperty("email").toEqualTypeOf<string>();
    expectTypeOf<Me>().toHaveProperty("first_name").toEqualTypeOf<string>();
    expectTypeOf<Me>().toHaveProperty("last_name").toEqualTypeOf<string>();
    expectTypeOf<Me>().toHaveProperty("role");
    expectTypeOf<Me>().toHaveProperty("direction_code").toEqualTypeOf<string>();
    expectTypeOf<Me>().toHaveProperty("fonction").toEqualTypeOf<string>();
  });

  it("exposes the ApiError component mirroring the API error format", () => {
    expectTypeOf<ApiErrorBody["detail"]>().toEqualTypeOf<string>();
    expectTypeOf<ApiErrorBody["errors"]>().toEqualTypeOf<Record<string, string[]>>();
  });

  it("declares the me and health paths", () => {
    expectTypeOf<keyof paths>().toExtend<string>();
    expectTypeOf<paths>().toHaveProperty("/api/v1/me/");
    expectTypeOf<paths>().toHaveProperty("/api/v1/health/");
  });
});
