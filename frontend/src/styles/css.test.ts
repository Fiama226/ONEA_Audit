import { readFileSync } from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";
import { fr } from "@/i18n/fr";

const read = (name: string) => readFileSync(path.resolve(import.meta.dirname, name), "utf8");

describe("stylesheets", () => {
  it("prints the footer and page counter from fr.ts wording", () => {
    expect(read("print.css")).toContain(
      `content: "${fr.impression.footer} " counter(page) " ${fr.impression.pageSep} " counter(pages);`,
    );
  });

  it("never applies the dark token set when printing", () => {
    const css = read("tokens.css");
    const dark = css.indexOf(".dark {");
    expect(css.lastIndexOf("@media not print", dark)).toBeGreaterThan(-1);
    expect(css.slice(css.lastIndexOf("@media not print", dark), dark)).not.toContain("}");
  });
});
