import { cn } from "@/lib/utils";

export type Chip = { value: string; label: string };

type Props = {
  label: string;
  chips: readonly Chip[];
  /** Valeur sélectionnée ; chaîne vide = « Toutes ». */
  value: string;
  onChange: (value: string) => void;
};

/**
 * Pastilles de filtre exclusives (un seul statut à la fois). L'état est dit par `aria-pressed`
 * et par la mise en forme (fond plein), jamais par la couleur seule.
 */
export function StatusChips({ label, chips, value, onChange }: Props) {
  return (
    <div role="group" aria-label={label} className="flex flex-wrap items-center gap-2">
      {chips.map((chip) => {
        const active = chip.value === value;
        return (
          <button
            key={chip.value || "all"}
            type="button"
            aria-pressed={active}
            onClick={() => onChange(chip.value)}
            className={cn(
              "inline-flex min-h-8 items-center rounded-full border px-3 text-sm font-medium transition-colors",
              active
                ? "border-primary bg-primary text-primary-foreground"
                : "border-border bg-surface text-foreground hover:bg-surface-subtle",
            )}
          >
            {chip.label}
          </button>
        );
      })}
    </div>
  );
}
