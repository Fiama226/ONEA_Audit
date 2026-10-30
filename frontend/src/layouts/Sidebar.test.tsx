import { screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { ROLES, type Role } from "@/auth/types";
import { fr } from "@/i18n/fr";
import { renderWithAuth } from "@/test/shell";
import { Sidebar } from "./Sidebar";

const HIDDEN: Record<Role, string[]> = {
  // Lot 8 : le suivi des recommandations est interdit à l'ADMIN (403 serveur).
  ADMIN: [fr.nav.missions, fr.nav.documents, fr.nav.recommandations],
  RAI: [fr.nav.administration],
  AUDITEUR: [fr.nav.administration, fr.nav.documentTemplates],
  AUDITE: [
    fr.nav.programmeAnnuel,
    fr.nav.referentiel,
    fr.nav.administration,
    fr.nav.documentTemplates,
  ],
  DG: [fr.nav.missions, fr.nav.documents, fr.nav.administration, fr.nav.documentTemplates],
};
const ALL = [
  fr.nav.dashboard,
  fr.nav.programmeAnnuel,
  fr.nav.missions,
  fr.nav.referentiel,
  fr.nav.recommandations,
  fr.nav.documents,
  fr.nav.administration,
  fr.nav.documentTemplates,
];

function renderSidebar(role: Role, path = "/") {
  renderWithAuth(<Sidebar collapsed={false} onToggle={() => {}} />, role, path);
  return within(screen.getByRole("navigation", { name: fr.nav.primary }));
}

describe("Sidebar", () => {
  it.each(ROLES)("shows only the entries allowed for %s", (role) => {
    const nav = renderSidebar(role);
    for (const label of ALL) {
      const present = !HIDDEN[role].includes(label);
      expect(nav.queryByRole("link", { name: label }) !== null, `${role} / ${label}`).toBe(present);
    }
  });

  it("gives AUDITE neither Référentiel nor Administration", () => {
    const nav = renderSidebar("AUDITE");
    expect(nav.queryByText(fr.nav.referentiel)).not.toBeInTheDocument();
    expect(nav.queryByText(fr.nav.administration)).not.toBeInTheDocument();
  });

  it("gives ADMIN the four entries plus the templates", () => {
    const nav = renderSidebar("ADMIN");
    expect(nav.getAllByRole("link")).toHaveLength(5);
  });

  it("marks only the templates entry current under /administration/documents", () => {
    const nav = renderSidebar("ADMIN", "/administration/documents/numerotation");
    expect(nav.getByRole("link", { name: fr.nav.documentTemplates })).toHaveAttribute(
      "aria-current",
      "page",
    );
    expect(nav.getByRole("link", { name: fr.nav.administration })).not.toHaveAttribute(
      "aria-current",
      "page",
    );
  });

  it("lists Programme annuel before Missions", () => {
    const nav = renderSidebar("RAI");
    const names = nav.getAllByRole("link").map((l) => l.textContent);
    expect(names.indexOf(fr.nav.programmeAnnuel)).toBeGreaterThanOrEqual(0);
    expect(names.indexOf(fr.nav.programmeAnnuel)).toBeLessThan(names.indexOf(fr.nav.missions));
  });

  it("removes the heading of a group whose entries are all hidden", () => {
    const nav = renderSidebar("AUDITEUR");
    expect(nav.queryByText(fr.nav.groupSettings)).not.toBeInTheDocument();
    expect(nav.getByText(fr.nav.groupMissions)).toBeInTheDocument();
  });

  it("marks the current page with aria-current", () => {
    const nav = renderSidebar("RAI", "/missions");
    expect(nav.getByRole("link", { name: fr.nav.missions })).toHaveAttribute(
      "aria-current",
      "page",
    );
    expect(nav.getByRole("link", { name: fr.nav.dashboard })).not.toHaveAttribute("aria-current");
  });

  it("keeps accessible labels when collapsed and exposes the state once", () => {
    renderWithAuth(<Sidebar collapsed onToggle={() => {}} />, "RAI");
    expect(screen.getByRole("link", { name: fr.nav.missions })).toBeInTheDocument();
    const toggle = screen.getByRole("button", { name: fr.shell.toggleMenu });
    expect(toggle).toHaveAttribute("aria-expanded", "false");
  });
});
