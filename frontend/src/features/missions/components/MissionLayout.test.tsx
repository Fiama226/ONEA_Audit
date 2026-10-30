import { screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { fr } from "@/i18n/fr";
import { allRights, aMission, MISSION_ID, missionHandlers, renderMission } from "../testUtils";

const PATH = `/missions/${MISSION_ID}/reunions`;

describe("MissionLayout tabs", () => {
  it("shows the audit framework tab to the RAI", async () => {
    renderMission(PATH, "RAI", { handlers: missionHandlers(aMission()) });
    const link = await screen.findByRole("link", { name: fr.missions.tabAuditFramework });
    expect(link).toHaveAttribute("href", `/missions/${MISSION_ID}/referentiel-audit`);
  });

  it("shows the audit framework tab to an auditee who cannot see the work tabs", async () => {
    const mission = aMission({ mes_droits: allRights(false) });
    renderMission(PATH, "AUDITE", { handlers: missionHandlers(mission) });
    expect(
      await screen.findByRole("link", { name: fr.missions.tabAuditFramework }),
    ).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: fr.missions.tabTeam })).not.toBeInTheDocument();
  });

  it.each(["RAPPORT_DIFFUSE", "EN_SUIVI", "CLOTUREE"] as const)(
    "shows the recommendation follow-up tab once the mission is %s",
    async (statut) => {
      renderMission(PATH, "RAI", { handlers: missionHandlers(aMission({ statut })) });
      const link = await screen.findByRole("link", { name: fr.suivi.tabFollowUp });
      expect(link).toHaveAttribute("href", `/missions/${MISSION_ID}/suivi-recommandations`);
    },
  );

  it("hides the recommendation follow-up tab before the report is distributed", async () => {
    renderMission(PATH, "RAI", {
      handlers: missionHandlers(aMission({ statut: "EN_COMMUNICATION" })),
    });
    await screen.findByRole("link", { name: fr.missions.tabAuditFramework });
    expect(screen.queryByRole("link", { name: fr.suivi.tabFollowUp })).not.toBeInTheDocument();
  });
});
