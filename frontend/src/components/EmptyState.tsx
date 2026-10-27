import { Clock } from "lucide-react";
import { useId, type ComponentType, type ReactNode } from "react";
import { Button } from "@/components/ui/button";
import { WaterRipple } from "@/components/illustrations/WaterRipple";
import { cn } from "@/lib/utils";

export type DisabledAction = {
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
  /** Action active (à utiliser quand la fonctionnalité existe). */
  children?: ReactNode;
  illustration?: boolean;
  headingLevel?: 1 | 2;
  className?: string;
};

export function EmptyState({
  title,
  description,
  action,
  children,
  illustration = true,
  headingLevel = 2,
  className,
}: Props) {
  const id = useId();
  const noteId = `${id}-note`;
  const Heading = headingLevel === 1 ? "h1" : "h2";
  const Icon = action?.icon;

  return (
    <section
      aria-labelledby={id}
      className={cn(
        "grid items-center gap-12 rounded-lg border border-border bg-surface px-6 py-10 lg:grid-cols-[1fr_320px] lg:px-12",
        !illustration && "lg:grid-cols-1",
        className,
      )}
    >
      <div>
        <Heading id={id} className="text-xl font-semibold">
          {title}
        </Heading>
        {description && <p className="mt-2 max-w-[58ch] text-sm text-text-muted">{description}</p>}
        {(action || children) && (
          <div className="mt-6 flex flex-wrap items-center gap-3">
            {action && (
              <>
                <Button
                  type="button"
                  disabled
                  aria-describedby={noteId}
                  className="disabled:border disabled:border-border disabled:bg-surface-subtle disabled:text-text-muted disabled:opacity-100"
                >
                  {Icon && <Icon className="size-4" aria-hidden />}
                  {action.label}
                </Button>
                <span
                  id={noteId}
                  className="inline-flex h-6 items-center gap-1.5 rounded-sm border border-dashed border-border bg-background px-2 text-xs font-medium text-text-muted"
                >
                  <Clock className="size-3.5" aria-hidden />
                  {action.note}
                </span>
              </>
            )}
            {children}
          </div>
        )}
      </div>
      {illustration && <WaterRipple className="hidden w-80 lg:block" />}
    </section>
  );
}
