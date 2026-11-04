import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";
import { fr } from "@/i18n/fr";
import { aMission, allRights } from "../testUtils";
import { MissionHeader } from "./MissionHeader";

function setup(mission = aMission({ mes_droits: allRights(false) })) {
  return render(
    <QueryClientProvider client={new QueryClient()}>
      <MemoryRouter>
        <MissionHeader mission={mission} />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("MissionHeader", () => {
  it("shows reference, title, status and phase", () => {
    setup();
    expect(screen.getByText("MI-2026-001")).toBeInTheDocument();
    expect(screen.getByRole("heading", { level: 1, name: "Audit des achats" })).toBeInTheDocument();
    expect(screen.getAllByText("En planification").length).toBeGreaterThan(0);
  });

  it("shows « Brouillon » when the mission has no reference yet", () => {
    setup(aMission({ reference: "", statut: "BROUILLON", mes_droits: allRights(false) }));
    expect(screen.getAllByText("Brouillon").length).toBeGreaterThan(0);
  });

  it("offers no action without any right", () => {
    setup();
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
  });

  it("offers only the actions granted by the server", async () => {
    setup(aMission({ mes_droits: { ...allRights(false), lancer: true } }));
    await userEvent.click(screen.getByRole("button", { name: fr.missions.actionsMenu }));
    const items = screen.getAllByRole("menuitem");
    expect(items).toHaveLength(1);
    expect(items[0]).toHaveTextContent("Lancer la mission");
  });

  it("shows the declaration banner only when the server asks for it", () => {
    const { unmount } = setup(
      aMission({ mes_droits: { ...allRights(false), confirmer_ma_declaration: true } }),
    );
    expect(screen.getByText(fr.missions.declarationBanner)).toBeInTheDocument();
    unmount();
    setup();
    expect(screen.queryByText(fr.missions.declarationBanner)).not.toBeInTheDocument();
  });

  describe("next action", () => {
    it("tells the RAI to plan a draft and offers the button", () => {
      setup(
        aMission({
          reference: "",
          statut: "BROUILLON",
          phase: null,
          etape_courante: null,
          mes_droits: { ...allRights(false), planifier: true, modifier: true },
        }),
      );
      expect(screen.getByRole("status", { name: fr.missions.nextActionLabel })).toHaveTextContent(
        fr.missions.nextDraft,
      );
      expect(screen.getByRole("button", { name: fr.missionPilotage.actionPlan })).toBeEnabled();
    });

    it("tells the RAI to launch a planned mission", () => {
      setup(
        aMission({
          statut: "PLANIFIEE",
          phase: null,
          mes_droits: { ...allRights(false), lancer: true },
        }),
      );
      expect(screen.getByRole("status", { name: fr.missions.nextActionLabel })).toHaveTextContent(
        fr.missions.nextPlanned,
      );
      expect(screen.getByRole("button", { name: fr.missionPilotage.actionLaunch })).toBeEnabled();
    });

    it("points to the order of mission, then to the current step", () => {
      const { unmount } = setup(
        aMission({
          etape_courante: { numero: 1, romain: "I" },
          mes_droits: { ...allRights(false), emettre_ordre: true, voir_travaux: true },
        }),
      );
      expect(
        screen.getByRole("link", { name: fr.missionPilotage.actionIssueOrder }),
      ).toHaveAttribute("href", expect.stringMatching(/\/etapes\/1$/));
      unmount();
      setup(
        aMission({
          etape_courante: { numero: 4, romain: "IV" },
          mes_droits: { ...allRights(false), voir_travaux: true },
        }),
      );
      expect(screen.getByRole("link", { name: /Ouvrir l'étape IV/ })).toHaveAttribute(
        "href",
        expect.stringMatching(/\/etapes\/4$/),
      );
    });

    it("shows nothing for a closed mission and names the phase honestly", () => {
      setup(aMission({ statut: "CLOTUREE", phase: null, mes_droits: allRights(false) }));
      expect(
        screen.queryByRole("status", { name: fr.missions.nextActionLabel }),
      ).not.toBeInTheDocument();
      expect(screen.queryByText("Hors phase")).not.toBeInTheDocument();
      expect(screen.getByText(fr.missions.phaseDone)).toBeInTheDocument();
    });

    it("does not offer a button the server did not grant", () => {
      setup(aMission({ statut: "PLANIFIEE", phase: null, mes_droits: allRights(false) }));
      expect(screen.queryByRole("button")).not.toBeInTheDocument();
    });
  });
});
