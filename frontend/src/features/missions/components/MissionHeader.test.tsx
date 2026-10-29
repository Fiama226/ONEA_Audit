import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";
import { fr } from "@/i18n/fr";
import { aMission, allRights } from "../testUtils";
import { MissionHeader } from "./MissionHeader";

function setup(mission = aMission({ mes_droits: allRights(false) })) {
  return render(
    <MemoryRouter>
      <MissionHeader mission={mission} />
    </MemoryRouter>,
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
});
