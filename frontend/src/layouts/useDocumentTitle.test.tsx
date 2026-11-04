import { describe, expect, it } from "vitest";
import { fr } from "@/i18n/fr";
import { renderWithAuth } from "@/test/shell";
import { documentTitleFor, useDocumentTitle } from "./useDocumentTitle";

function Probe() {
  useDocumentTitle();
  return null;
}

describe("documentTitleFor", () => {
  it("names the dashboard", () => {
    expect(documentTitleFor("/")).toBe(`${fr.nav.dashboard} - ${fr.shell.appTitle}`);
  });

  it("names the page then its section", () => {
    expect(documentTitleFor("/missions")).toBe(`${fr.nav.missions} - ${fr.shell.appTitle}`);
    expect(documentTitleFor("/administration/utilisateurs")).toMatch(
      /^Utilisateurs - Administration - /,
    );
  });

  it("distinguishes a mission step from the mission", () => {
    expect(documentTitleFor("/missions/abc/etapes/4")).toMatch(/^Étape IV - /);
  });
});

describe("useDocumentTitle", () => {
  it("sets the tab title from the current route", () => {
    renderWithAuth(<Probe />, "RAI", "/missions");
    expect(document.title).toBe(`${fr.nav.missions} - ${fr.shell.appTitle}`);
  });
});
