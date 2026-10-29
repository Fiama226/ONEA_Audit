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
});
