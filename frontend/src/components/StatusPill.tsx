import { cn } from "@/lib/utils";

export type PillTone = "neutral" | "progress" | "warning" | "success" | "danger";

const TONES: Record<PillTone, { text: string; dot: string }> = {
  neutral: { text: "text-text-muted", dot: "bg-text-muted" },
  progress: { text: "text-primary", dot: "bg-primary" },
  warning: { text: "text-warning-text", dot: "bg-warning" },
  success: { text: "text-success-text", dot: "bg-success" },
  danger: { text: "text-destructive", dot: "bg-destructive" },
};

/** Pastille de statut : point de couleur et libellé (jamais la couleur seule). */
export function StatusPill({
  label,
  tone,
  className,
}: {
  label: string;
  tone: PillTone;
  className?: string;
}) {
  const style = TONES[tone];
  return (
    <span
      className={cn(
        "inline-flex h-6 items-center gap-1.5 rounded-full border border-border bg-surface px-2.5 text-xs font-medium whitespace-nowrap",
        style.text,
        className,
      )}
    >
      <span className={cn("size-2 rounded-full", style.dot)} aria-hidden />
      {label}
    </span>
  );
}
