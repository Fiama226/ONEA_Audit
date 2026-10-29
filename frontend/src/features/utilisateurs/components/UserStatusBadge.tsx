import { cn } from "@/lib/utils";
import { STATUS_LABELS } from "../labels";

type Status = keyof typeof STATUS_LABELS;

const STYLE: Record<Status, { text: string; dot: string }> = {
  actif: { text: "text-success-text", dot: "bg-success" },
  inactif: { text: "text-text-muted", dot: "bg-text-muted" },
  attente: { text: "text-warning-text", dot: "bg-warning" },
};

/** Statut d'un compte : point de couleur et libellé (jamais la couleur seule). */
export function UserStatusBadge({
  active,
  pendingFirstLogin = false,
}: {
  active: boolean;
  pendingFirstLogin?: boolean;
}) {
  const status: Status = !active ? "inactif" : pendingFirstLogin ? "attente" : "actif";
  const style = STYLE[status];
  return (
    <span
      className={cn(
        "inline-flex h-6 items-center gap-1.5 rounded-full border border-border bg-surface px-2.5 text-xs font-medium",
        style.text,
      )}
    >
      <span className={cn("size-2 rounded-full", style.dot)} aria-hidden />
      {STATUS_LABELS[status]}
    </span>
  );
}
