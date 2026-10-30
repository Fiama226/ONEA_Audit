import { configure, render, screen } from "@testing-library/react";
import { beforeAll, describe, expect, it, vi } from "vitest";
import { axe } from "vitest-axe";
import { fr } from "@/i18n/fr";
import { renderRoutes } from "@/test/shell";
import { AppShell } from "./AppShell";
import { PrintLayout } from "./PrintLayout";

beforeAll(() => {
  vi.setConfig({ testTimeout: 20000 });
  configure({ asyncUtilTimeout: 15000 });
});

const doc = (
  <PrintLayout
    reference="MIS-2026-001"
    documentType="Rapport d'audit"
    printedBy="A. Ouedraogo"
    printedAt="27/10/2026 à 08:14"
  >
    <p>Contenu du document</p>
  </PrintLayout>
);

describe("PrintLayout", () => {
  it("renders the mission reference, the body and the confidentiality note", () => {
    render(doc);
    expect(screen.getByText("MIS-2026-001")).toBeInTheDocument();
    expect(screen.getByText("Rapport d'audit")).toBeInTheDocument();
    expect(screen.getByText("Contenu du document")).toBeInTheDocument();
    expect(screen.getByText("CONFIDENTIEL · USAGE INTERNE ONEA")).toBeInTheDocument();
    expect(screen.getByText(fr.print.organisation)).toBeInTheDocument();
    expect(
      screen.getByText(/Imprimé le 27\/10\/2026 à 08:14 par A\. Ouedraogo/),
    ).toBeInTheDocument();
    expect(screen.getByRole("banner")).toBeInTheDocument();
    expect(screen.getByRole("contentinfo")).toBeInTheDocument();
  });

  it("does not own the main landmark", () => {
    const { container } = render(doc);
    expect(container.querySelector("main")).toBeNull();
  });

  it("never overlays the content with fixed header or footer", () => {
    const { container } = render(doc);
    expect(container.innerHTML).not.toMatch(/print:fixed/);
  });

  it("has no landmark violation inside the app shell", async () => {
    const { container } = renderRoutes(
      [{ element: <AppShell />, children: [{ path: "/", element: doc }] }],
      "RAI",
    );
    expect(container.querySelectorAll("main")).toHaveLength(1);
    const results = await axe(container, { rules: { "color-contrast": { enabled: false } } });
    expect(results.violations).toEqual([]);
  });
});
