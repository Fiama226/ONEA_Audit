import { describe, expect, it } from "vitest";
import type { Role } from "@/auth/types";
import { fr } from "@/i18n/fr";
import { navFor, rolesFor } from "./navigation";

const labels = (role: Role) =>
  navFor(role)
    .flatMap((g) => g.items)
    .map((i) => i.label);

describe("navigation du lot 7", () => {
  it("limite /rapports à RAI, AUDITEUR, AUDITE et DG", () => {
    expect(rolesFor("/rapports")).toEqual(["RAI", "AUDITEUR", "AUDITE", "DG"]);
  });

  it("montre « Rapports diffusés » au DG, sans « Missions »", () => {
    expect(labels("DG")).toContain(fr.communication.navDistributed);
    expect(labels("DG")).not.toContain(fr.nav.missions);
  });

  it("ne montre pas « Rapports diffusés » à l'ADMIN", () => {
    expect(labels("ADMIN")).not.toContain(fr.communication.navDistributed);
  });
});

describe("navigation : mode de signature et piste d'audit", () => {
  it("rend /administration/signatures accessible depuis le menu de l'ADMIN et du RAI", () => {
    expect(labels("ADMIN")).toContain(fr.signatureAdmin.title);
    expect(labels("RAI")).toContain(fr.signatureAdmin.title);
    expect(labels("AUDITEUR")).not.toContain(fr.signatureAdmin.title);
    expect(labels("DG")).not.toContain(fr.signatureAdmin.title);
  });
});
