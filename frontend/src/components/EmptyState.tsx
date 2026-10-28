import { Clock } from "lucide-react";
import { useId, type ComponentType, type ReactNode } from "react";
import { Button } from "@/components/ui/button";
import { WaterRipple } from "@/components/illustrations/WaterRipple";
import { cn } from "@/lib/utils";

type DisabledAction = {
  label: string;
  icon?: ComponentType<{ className?: string; "aria-hidden"?: boolean }>;
  /** Pastille de disponibilité (ex. « Disponible au lot 3 »), reliée au bouton par aria-describedby. */
  note: string;
};

type Props = {
  title: string;
  description?: string;
  /** Action principale désactivée accompagnée de sa pastille. */
  action?: DisabledAction;
  illustration?: boolean;
  /** Actions actives (boutons, liens) affichées sous la description. */
  children?: ReactNode;
};

export function EmptyState({ title, description, action, illustration = true, children }: Props) {
  const id = useId();
  const noteId = `${id}-note`;
  const Icon = action?.icon;

  return (
    <section
      aria-labelledby={id}
      className={cn(
        "grid items-center gap-12 rounded-lg border border-border bg-surface px-6 py-10 lg:px-12",
        illustration ? "lg:grid-cols-[1fr_320px]" : "lg:grid-cols-1",
      )}
    >
      <div>
        <h2 id={id} className="text-xl font-semibold">
          {title}
        </h2>
        {description && <p className="mt-2 max-w-[58ch] text-sm text-text-muted">{description}</p>}
        {action && (
          <div className="mt-6 flex flex-wrap items-center gap-3">
            {/* L'enveloppe porte le curseur : un bouton désactivé ne reçoit pas d'événements. */}
            <span className="cursor-not-allowed">
              <Button
                type="button"
                disabled
                aria-describedby={noteId}
                className="border border-border bg-surface-subtle text-text-muted disabled:opacity-100"
              >
                {Icon && <Icon className="size-4" aria-hidden />}
                {action.label}
              </Button>
            </span>
            <span
              id={noteId}
              className="inline-flex h-6 items-center gap-1.5 rounded-sm border border-dashed border-border bg-background px-2 text-xs font-medium text-text-muted"
            >
              <Clock className="size-3.5" aria-hidden />
              {action.note}
            </span>
          </div>
        )}
        {children && <div className="mt-6 flex flex-wrap items-center gap-3">{children}</div>}
      </div>
      {illustration && <WaterRipple className="hidden w-80 lg:block" />}
    </section>
  );
}
