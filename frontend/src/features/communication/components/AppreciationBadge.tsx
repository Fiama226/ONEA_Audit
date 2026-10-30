import { StatusPill, type PillTone } from "@/components/StatusPill";
import { APPRECIATION_LABELS } from "../labels";
import type { AppreciationGlobale } from "../types";

const TONE: Record<AppreciationGlobale, PillTone> = {
  MAITRISE: "success",
  PERFECTIBLE: "warning",
  INSUFFISANTE: "danger",
};

/** Appréciation globale du dispositif ; absente tant que le rapport n'en porte pas. */
export function AppreciationBadge({ appreciation }: { appreciation: AppreciationGlobale | "" }) {
  if (appreciation === "") return null;
  return <StatusPill label={APPRECIATION_LABELS[appreciation]} tone={TONE[appreciation]} />;
}
