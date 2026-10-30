import type { LucideIcon } from "lucide-react";
import { fr } from "@/i18n/fr";
import { cn } from "@/lib/utils";
import { fmtInt } from "./palette";

export type StatTone = "neutral" | "warning" | "danger" | "success";

const ICON_TONE: Record<StatTone, string> = {
  neutral: "text-text-muted",
  warning: "text-warning-text",
  danger: "text-destructive",
  success: "text-success-text",
};

/** Indicateur chiffré. La valeur reste en `text-foreground` ; le ton passe par l'icône. */
export function StatTile({
  label,
  value,
  format = fmtInt,
  hint,
  tone = "neutral",
  icon: Icon,
}: {
  label: string;
  value: number | null;
  format?: (n: number) => string;
  hint?: string;
  tone?: StatTone;
  icon?: LucideIcon;
}) {
  if (tone !== "neutral" && !Icon) {
    throw new Error(
      `StatTile « ${label} » : un ton « ${tone} » exige une icône (jamais la couleur seule).`,
    );
  }
  return (
    <div className="rounded-lg border border-border bg-surface p-4">
      <div className="flex items-center gap-2 text-sm text-text-muted">
        {Icon && <Icon aria-hidden="true" className={cn("size-4", ICON_TONE[tone])} />}
        <span>{label}</span>
      </div>
      <p className="mt-1 text-2xl font-semibold text-foreground tabular-nums">
        {value === null ? fr.charts.none : format(value)}
      </p>
      {hint && <p className="mt-1 text-xs text-text-muted">{hint}</p>}
    </div>
  );
}
