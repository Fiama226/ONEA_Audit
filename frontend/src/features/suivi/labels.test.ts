import { describe, expect, it } from "vitest";
import { fr } from "@/i18n/fr";
import {
  EVENEMENT_LABELS,
  PRIORITE_LABELS,
  STATUT_RECOMMANDATION_SUIVI_LABELS,
  STATUT_REPORT_LABELS,
  STATUT_SUIVI_LABELS,
  TRANSITION_FIELD,
} from "./labels";
import type { StatutSuivi } from "./types";

const STATUTS: StatutSuivi[] = [
  "A_LANCER",
  "EN_COURS",
  "REALISEE",
  "VERIFIEE",
  "CLOTUREE",
  "ABANDON_PROPOSE",
  "ABANDONNEE",
];

describe("libellés du suivi", () => {
  it("donne un libellé français à chaque statut de suivi (R2)", () => {
    expect(Object.keys(STATUT_SUIVI_LABELS).sort()).toEqual([...STATUTS].sort());
    expect(STATUT_SUIVI_LABELS.REALISEE).toBe("Réalisée, à vérifier");
    expect(STATUT_SUIVI_LABELS.ABANDONNEE).toBe("Abandonnée (justifiée)");
    for (const label of Object.values(STATUT_SUIVI_LABELS)) expect(label).toMatch(/^\p{Lu}/u);
  });

  it("n'a aucun libellé vide ni en clé technique", () => {
    const all = [
      ...Object.values(STATUT_SUIVI_LABELS),
      ...Object.values(STATUT_RECOMMANDATION_SUIVI_LABELS),
      ...Object.values(PRIORITE_LABELS),
      ...Object.values(STATUT_REPORT_LABELS),
      ...Object.values(EVENEMENT_LABELS),
    ];
    for (const label of all) {
      expect(label).not.toBe("");
      expect(label).not.toMatch(/^[A-Z_]+$/);
    }
  });

  it("couvre les neuf transitions et leur champ de corps", () => {
    expect(Object.keys(TRANSITION_FIELD).sort()).toEqual(
      [
        "accept-abandon",
        "close",
        "comment",
        "declare-done",
        "propose-abandon",
        "reject",
        "reopen",
        "start",
        "verify",
      ].sort(),
    );
    expect(TRANSITION_FIELD["propose-abandon"]).toBe("justification");
    expect(TRANSITION_FIELD.reject).toBe("motif");
    expect(TRANSITION_FIELD.comment).toBe("texte");
  });

  it("réserve une section vide par tâche parallèle", () => {
    expect(fr.suiviRegistre).toEqual({});
    expect(fr.rechercheNotifications).toEqual({});
    expect(fr.tableauxDirection).toEqual({});
    expect(fr.tableauxEquipe).toEqual({});
  });
});
