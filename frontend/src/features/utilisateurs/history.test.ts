import { describe, expect, it } from "vitest";
import type { components } from "@/api/schema";
import { describeAction, describeChanges, historyKey } from "./history";

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
    action_metier: null,
    motif: null,
    affaiblissement: null,
  };
}

describe("historyKey", () => {
  it("is prefixed by utilisateurs so mutations can invalidate it", () => {
    expect(historyKey(7, 2)).toEqual(["utilisateurs", "history", 7, 2]);
  });
});

describe("describeAction", () => {
  it.each([
    ["creation_compte", "Création du compte"],
    ["reinitialisation_mot_de_passe", "Réinitialisation du mot de passe par l'administration"],
    ["desactivation_otp", "Désactivation du code de connexion par courriel"],
    ["activation_otp", "Activation du code de connexion par courriel"],
    ["changement_role", "Changement de rôle"],
    ["amorcage_administrateur", "Création ou reprise du compte administrateur (serveur)"],
    ["mot_de_passe_temporaire_migration", "Mot de passe temporaire attribué (migration)"],
    ["changement_mot_de_passe", "Changement du mot de passe par l'agent"],
    ["changement_mot_de_passe_impose", "Remplacement du mot de passe temporaire par l'agent"],
    [
      "reinitialisation_par_code",
      "Réinitialisation du mot de passe par code (mot de passe oublié)",
    ],
  ])("labels the business action %s in French", (metier, label) => {
    expect(describeAction({ ...entry({}), action_metier: metier })).toBe(label);
  });

  it("falls back to the auditlog operation when there is no business action", () => {
    expect(describeAction(entry({}))).toBe("Modification");
    expect(describeAction({ ...entry({}), action: "create" })).toBe("Création");
  });

  it("shows an unknown business action as is", () => {
    expect(describeAction({ ...entry({}), action_metier: "action_future" })).toBe("action_future");
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
      { field: "role", label: "Rôle", before: "Audité", after: "Auditeur" },
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
    expect(lines[0]?.after).toBe("Ajout : a, b");
  });

  it("drops id and unchanged blank lines on a real creation payload", () => {
    const e = entry({
      id: ["None", "7"],
      username: ["None", "auditeur2"],
      email: ["None", ""],
      first_name: ["None", ""],
      is_active: ["None", "True"],
    });
    expect(describeChanges(e)).toEqual([
      { field: "username", label: "Identifiant", before: "—", after: "auditeur2" },
      { field: "is_active", label: "Statut du compte", before: "—", after: "Actif" },
    ]);
  });
});

describe("describeChanges — création d'un compte", () => {
  it("masque les relations inverses et les indicateurs internes, et traduit le rôle provisoire", () => {
    const e = entry({
      username: ["None", "qa-adm-u1"],
      notifications: ["None", "notifications.Notification.None"],
      suivis_responsable: ["None", "suivi.SuiviAction.None"],
      affectations_mission: ["None", "missions.AffectationMission.None"],
      keycloak_sync_manuel: ["None", "False"],
      role_provisoire: ["None", "True"],
    });
    expect(describeChanges(e)).toEqual([
      { field: "username", label: "Identifiant", before: "—", after: "qa-adm-u1" },
      { field: "role_provisoire", label: "Rôle provisoire", before: "—", after: "Oui" },
    ]);
  });
});

describe("describeChanges — authentification interne", () => {
  it("traduit l'origine, le code de connexion, le mot de passe temporaire et les dates", () => {
    const e = entry({
      origine: ["None", "ADMINISTRATION"],
      otp_connexion_actif: ["False", "True"],
      doit_changer_mot_de_passe: ["True", "False"],
      mot_de_passe_expire_le: ["None", "2026-11-07 08:00:00+00:00"],
      verrouille_jusqu_a: ["2026-11-04 10:15:00+00:00", "None"],
    });
    expect(describeChanges(e)).toEqual([
      {
        field: "origine",
        label: "Origine du compte",
        before: "—",
        after: "Création par l'administration",
      },
      {
        field: "otp_connexion_actif",
        label: "Code de connexion par courriel",
        before: "Non",
        after: "Oui",
      },
      {
        field: "doit_changer_mot_de_passe",
        label: "Mot de passe temporaire à changer",
        before: "Oui",
        after: "Non",
      },
      {
        field: "mot_de_passe_expire_le",
        label: "Expiration du mot de passe temporaire",
        before: "—",
        after: "07/11/2026 08:00",
      },
      {
        field: "verrouille_jusqu_a",
        label: "Connexion bloquée jusqu'au",
        before: "04/11/2026 10:15",
        after: "—",
      },
    ]);
  });
});
