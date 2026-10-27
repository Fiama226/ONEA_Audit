import { fr } from "@/i18n/fr";

/** Les 18 étapes IFACI en trois phases ; les jalons sont validés par le RAI. */
export const MILESTONES: readonly string[] = ["VI", "X", "XIII", "XVIII"];

export type Phase = { name: string; range: string; steps: string[] };

export const PHASES: Phase[] = [
  {
    name: fr.dashboard.phasePlanning,
    range: `${fr.dashboard.stepsRange} I à X`,
    steps: ["I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X"],
  },
  {
    name: fr.dashboard.phaseFieldwork,
    range: `${fr.dashboard.stepsRange} XI à XIV`,
    steps: ["XI", "XII", "XIII", "XIV"],
  },
  {
    name: fr.dashboard.phaseReporting,
    range: `${fr.dashboard.stepsRange} XV à XVIII`,
    steps: ["XV", "XVI", "XVII", "XVIII"],
  },
];
