import { fr } from "@/i18n/fr";

/** Les 18 étapes IFACI en trois phases ; les jalons sont validés par le RAI. */
export const MILESTONES: readonly string[] = ["VI", "X", "XIII", "XVIII"];

export type Phase = { name: string; range: string; steps: string[] };

export const PHASES: Phase[] = [
  {
    name: fr.dashboard.phasePlanning,
    range: fr.dashboard.rangePlanning,
    steps: ["I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X"],
  },
  {
    name: fr.dashboard.phaseFieldwork,
    range: fr.dashboard.rangeFieldwork,
    steps: ["XI", "XII", "XIII", "XIV"],
  },
  {
    name: fr.dashboard.phaseReporting,
    range: fr.dashboard.rangeReporting,
    steps: ["XV", "XVI", "XVII", "XVIII"],
  },
];
