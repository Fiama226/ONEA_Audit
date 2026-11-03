import { readdirSync, readFileSync, statSync } from "node:fs";
import { join, relative, sep } from "node:path";
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { axe } from "vitest-axe";
import { ScrollRegion } from "./scroll-region";

describe("ScrollRegion", () => {
  it("est focusable et nommé pour le défilement au clavier", async () => {
    const { container } = render(
      <ScrollRegion label="Tableau des essais">
        <table>
          <caption>Tableau des essais</caption>
          <tbody>
            <tr>
              <td>1</td>
            </tr>
          </tbody>
        </table>
      </ScrollRegion>,
    );
    const region = screen.getByRole("group", { name: "Tableau des essais" });
    expect(region).toHaveAttribute("tabindex", "0");
    expect(region).toHaveClass("overflow-x-auto");
    const results = await axe(container, { rules: { "color-contrast": { enabled: false } } });
    expect(results.violations).toEqual([]);
  });
});

/** Seuls ces fichiers peuvent déclarer `overflow-x-auto` eux-mêmes (conteneurs déjà focusables). */
const ALLOWED = new Set([
  "components/ui/scroll-region.tsx",
  "components/ui/table.tsx",
  "components/DataTable.tsx",
  "features/programmation/components/AuditPlanCalendar.tsx",
]);

function sources(dir: string): string[] {
  return readdirSync(dir).flatMap((name) => {
    const path = join(dir, name);
    if (statSync(path).isDirectory()) return sources(path);
    return path.endsWith(".tsx") && !path.endsWith(".test.tsx") ? [path] : [];
  });
}

describe("conteneurs à défilement horizontal", () => {
  it("passent tous par ScrollRegion (focusables et nommés, WCAG 2.1.1)", () => {
    const root = join(process.cwd(), "src");
    const offenders = sources(root)
      .filter((file) => readFileSync(file, "utf-8").includes("overflow-x-auto"))
      .map((file) => relative(root, file).split(sep).join("/"))
      .filter((file) => !ALLOWED.has(file));
    expect(offenders).toEqual([]);
  });
});
