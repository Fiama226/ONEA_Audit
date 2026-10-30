import { StatusPill, type PillTone } from "@/components/StatusPill";
import { CONCLUSION_LABELS } from "../labels";
import type { ConclusionTest } from "../types";

const TONE: Record<ConclusionTest, PillTone> = {
  SATISFAISANT: "success",
  POINT_FORT: "progress",
  ANOMALIE: "danger",
};

/** Conclusion d'un test (absente tant que la fiche n'est pas conclue). */
export function ConclusionBadge({ conclusion }: { conclusion: ConclusionTest | "" | undefined }) {
  if (!conclusion) return <span className="text-sm text-text-muted">—</span>;
  return <StatusPill label={CONCLUSION_LABELS[conclusion]} tone={TONE[conclusion]} />;
}
