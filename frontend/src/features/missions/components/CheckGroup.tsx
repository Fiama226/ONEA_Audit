import { useId } from "react";
import { ALERT_CLASS } from "@/components/form/FormField";
import { ListIncompleteAlert } from "@/components/ListIncompleteAlert";
import { Checkbox } from "@/components/ui/checkbox";
import { Label } from "@/components/ui/label";
import { fr } from "@/i18n/fr";

type Props = {
  legend: string;
  items: { id: string; label: string }[];
  count: number;
  isLoading: boolean;
  isError: boolean;
  value: string[];
  onChange: (value: string[]) => void;
  disabled?: boolean;
  help?: string;
};

/** Liste de cases à cocher dont toutes les pages sont chargées (alerte si la liste est tronquée). */
export function CheckGroup({
  legend,
  items,
  count,
  isLoading,
  isError,
  value,
  onChange,
  disabled,
  help,
}: Props) {
  const prefix = useId();
  return (
    <fieldset className="grid gap-2" disabled={disabled}>
      <legend className="text-sm font-medium">{legend}</legend>
      {help && <p className="text-xs text-text-muted">{help}</p>}
      {isError && (
        <p role="alert" className={ALERT_CLASS}>
          {fr.refStructure.loadError}
        </p>
      )}
      <ListIncompleteAlert count={count} loaded={items.length} />
      {isLoading && (
        <p role="status" className="text-sm text-text-muted">
          {fr.common.loading}
        </p>
      )}
      <ul className="grid max-h-56 gap-1 overflow-y-auto rounded-md border border-border p-2">
        {items.map((item) => {
          const inputId = `${prefix}-${item.id}`;
          return (
            <li key={item.id} className="flex items-center gap-2 text-sm">
              <Checkbox
                id={inputId}
                disabled={disabled}
                checked={value.includes(item.id)}
                onCheckedChange={(checked) =>
                  onChange(
                    checked === true ? [...value, item.id] : value.filter((v) => v !== item.id),
                  )
                }
              />
              <Label htmlFor={inputId} className="font-normal">
                {item.label}
              </Label>
            </li>
          );
        })}
      </ul>
    </fieldset>
  );
}
