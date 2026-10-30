import { readFileSync } from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";
import { contrastRatio, SERIES_STATUT } from "./palette";

const css = readFileSync(path.resolve(import.meta.dirname, "../../styles/tokens.css"), "utf8");
const lightBlock = css.slice(css.indexOf(":root {"), css.indexOf("@media not print"));
const darkBlock = css.slice(css.indexOf(".dark {"), css.indexOf("/* Mapping shadcn"));

function token(block: string, name: string, fallback: string): string {
  const m = new RegExp(`${name}:\\s*(#[0-9a-fA-F]{6})`).exec(block);
  return m?.[1] ?? fallback;
}

describe("contrastRatio", () => {
  it("matches WCAG reference values", () => {
    expect(contrastRatio("#000000", "#ffffff")).toBeCloseTo(21, 1);
    expect(contrastRatio("#ffffff", "#ffffff")).toBeCloseTo(1, 5);
  });
});

describe.each([
  ["clair", lightBlock],
  ["sombre", darkBlock],
])("tokens de graphique, mode %s", (_mode, block) => {
  const light = block === lightBlock;
  const surface = token(block, "--surface", "");
  const get = (n: string) => token(block, n, token(lightBlock, n, ""));

  it("texte ≥ 4,5:1 sur la surface", () => {
    for (const n of ["--foreground", "--text-muted", "--danger"]) {
      expect(contrastRatio(get(n), surface), n).toBeGreaterThanOrEqual(4.5);
    }
    const success = light ? get("--success-text") : get("--success");
    const warning = light ? get("--warning-text") : get("--warning");
    expect(contrastRatio(success, surface)).toBeGreaterThanOrEqual(4.5);
    expect(contrastRatio(warning, surface)).toBeGreaterThanOrEqual(4.5);
  });

  it("--chart-1, --chart-done et --chart-late ≥ 3:1 sur la surface", () => {
    for (const n of ["--chart-1", "--chart-done", "--chart-late"]) {
      expect(contrastRatio(get(n), surface), n).toBeGreaterThanOrEqual(3);
    }
  });
});

describe("SERIES_STATUT", () => {
  it("définit trois séries libellées avec une icône", () => {
    expect(Object.keys(SERIES_STATUT)).toEqual(["done", "open", "late"]);
    expect(SERIES_STATUT.done.label).toBe("Clôturées");
    expect(SERIES_STATUT.open.label).toBe("Ouvertes dans les délais");
    expect(SERIES_STATUT.late.label).toBe("En retard");
    for (const s of Object.values(SERIES_STATUT)) expect(s.icon).toBeTruthy();
  });
});
