import { describe, expect, it } from "vitest";
import type { components } from "@/api/schema";
import { describeChanges, historyKey } from "./history";

type AuditLog = components["schemas"]["AuditLog"];

function entry(changes: AuditLog["changes"]): AuditLog {
  return {
    id: 1,
    timestamp: "2026-10-28T08:00:00Z",
    actor: { id: 2, username: "admin" },
    action: "update",
    model: "users.user",
    object_id: "7",
    object_repr: "auditeur2",
    changes,
  };
}

describe("historyKey", () => {
  it("is prefixed by utilisateurs so mutations can invalidate it", () => {
    expect(historyKey(7, 2)).toEqual(["utilisateurs", "history", 7, 2]);
  });
});

describe("describeChanges", () => {
  it("describes a deactivation propagated to Keycloak and hides technical fields", () => {
    const e = entry({
      is_active: ["True", "False"],
      motif_desactivation: ["", "Départ"],
      desactive_par: ["None", "2"],
      keycloak_sync_statut: ["A_JOUR", "EN_ATTENTE"],
    });
    expect(describeChanges(e)).toEqual([
      { field: "is_active", label: "Statut du compte", before: "Actif", after: "Désactivé" },
      {
        field: "motif_desactivation",
        label: "Motif de désactivation",
        before: "—",
        after: "Départ",
      },
      {
        field: "keycloak_sync_statut",
        label: "Synchronisation Keycloak",
        before: "À jour",
        after: "En attente",
      },
    ]);
  });

  it("translates roles", () => {
    expect(describeChanges(entry({ role: ["AUDITE", "AUDITEUR"] }))).toEqual([
      { field: "role", label: "Rôle (annuaire)", before: "Audité", after: "Auditeur" },
    ]);
  });

  it("translates origin and shows None as a dash", () => {
    expect(describeChanges(entry({ origine: ["None", "CSV"] }))).toEqual([
      { field: "origine", label: "Origine du compte", before: "—", after: "Import CSV" },
    ]);
  });

  it("keeps unknown fields as-is", () => {
    expect(describeChanges(entry({ foo: ["a", "b"] }))).toEqual([
      { field: "foo", label: "foo", before: "a", after: "b" },
    ]);
  });

  it("does not crash on the raw shape", () => {
    const lines = describeChanges(entry({ role: { raw: "bizarre" } }));
    expect(lines).toHaveLength(1);
    expect(lines[0]?.after).toContain("bizarre");
  });

  it("handles the m2m shape", () => {
    const lines = describeChanges(
      entry({ groups: { type: "m2m", operation: "add", objects: ["a", "b"] } }),
    );
    expect(lines).toHaveLength(1);
    expect(lines[0]?.after).toContain("a");
  });
});
