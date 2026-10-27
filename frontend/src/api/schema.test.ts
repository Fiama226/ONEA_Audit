import { describe, expectTypeOf, it } from "vitest";

import type { components, paths } from "./schema";

type Me = components["schemas"]["Me"];
type ApiErrorBody = components["schemas"]["ApiError"];

// Type-level contract tests: a backend drift regenerates schema.d.ts and breaks `tsc`.
describe("generated OpenAPI types", () => {
  it("exposes the Me component with the expected fields", () => {
    expectTypeOf<Me["id"]>().toEqualTypeOf<number>();
    expectTypeOf<Me["username"]>().toEqualTypeOf<string>();
    expectTypeOf<Me["email"]>().toEqualTypeOf<string>();
    expectTypeOf<Me["first_name"]>().toEqualTypeOf<string>();
    expectTypeOf<Me["last_name"]>().toEqualTypeOf<string>();
    expectTypeOf<Me["role"]>().toEqualTypeOf<components["schemas"]["RoleEnum"]>();
    expectTypeOf<Me["direction_code"]>().toEqualTypeOf<string>();
    expectTypeOf<Me["fonction"]>().toEqualTypeOf<string>();
    expectTypeOf<keyof Me>().toEqualTypeOf<
      | "id"
      | "username"
      | "email"
      | "first_name"
      | "last_name"
      | "role"
      | "direction_code"
      | "fonction"
    >();
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
