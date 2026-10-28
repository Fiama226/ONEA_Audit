import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

describe("SEGMENT_LABELS", () => {
  it("declares no duplicate key", () => {
    const source = readFileSync(resolve(process.cwd(), "src/layouts/navigation.ts"), "utf8");
    const body = /SEGMENT_LABELS[^=]*=\s*\{([\s\S]*?)\n\};/.exec(source)?.[1] ?? "";
    const keys = [...body.matchAll(/^\s{2}("[^"]+"|[A-Za-z_]+):/gm)].map((m) => m[1]);
    expect(keys.length).toBeGreaterThan(10);
    expect(new Set(keys).size).toBe(keys.length);
  });
});
