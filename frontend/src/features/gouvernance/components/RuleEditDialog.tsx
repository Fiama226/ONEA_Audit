import { useId, useState } from "react";
import { isApiError } from "@/api/errors";
import { ALERT_CLASS, FormField } from "@/components/form/FormField";
import { NativeSelect } from "@/components/form/NativeSelect";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { fr } from "@/i18n/fr";
import { useUpdateGovernanceRule, type GovernanceRule } from "../api";
import { weakens } from "../strength";
import { FIELDS, fieldLabel, t, type RuleKey } from "../textes";

type Value = Record<string, unknown>;

function FieldControl({
  rule,
  field,
  value,
  error,
  onChange,
}: {
  rule: string;
  field: string;
  value: unknown;
  error?: string;
  onChange: (next: unknown) => void;
}) {
  const text = FIELDS[rule as RuleKey]?.[field];
  return (
    <FormField label={fieldLabel(rule, field)} help={text?.help} error={error}>
      {(p) =>
        typeof value === "boolean" ? (
          <NativeSelect
            {...p}
            value={value ? "true" : "false"}
            onChange={(e) => onChange(e.target.value === "true")}
          >
            <option value="true">{text?.yes ?? "Oui"}</option>
            <option value="false">{text?.no ?? "Non"}</option>
          </NativeSelect>
        ) : typeof value === "number" ? (
          <Input
            {...p}
            type="number"
            inputMode="numeric"
            step={1}
            value={String(value)}
            onChange={(e) => onChange(e.target.value === "" ? 0 : Number(e.target.value))}
          />
        ) : (
          <NativeSelect {...p} value={String(value)} onChange={(e) => onChange(e.target.value)}>
            {Object.entries(text?.values ?? {}).map(([code, label]) => (
              <option key={code} value={code}>
                {label}
              </option>
            ))}
          </NativeSelect>
        )
      }
    </FormField>
  );
}

/** Modification d'une règle (ADMIN) : champs de la règle, motif, refus du serveur affichés. */
export function RuleEditDialog({
  rule,
  onOpenChange,
}: {
  rule: GovernanceRule;
  onOpenChange: (open: boolean) => void;
}) {
  const id = useId();
  const update = useUpdateGovernanceRule();
  const current = rule.valeur as Value;
  const [draft, setDraft] = useState<Value>(() => ({ ...current }));
  const [motif, setMotif] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});

  const changed = Object.fromEntries(
    Object.entries(draft).filter(([field, value]) => value !== current[field]),
  );
  const weakening = weakens(rule.cle, current, draft);

  async function submit() {
    setError(null);
    setFieldErrors({});
    if (Object.keys(changed).length === 0) {
      setError(t.rules.unchanged);
      return;
    }
    if (weakening && !motif.trim()) {
      setFieldErrors({ motif: t.rules.weakeningNotice });
      return;
    }
    try {
      await update.mutateAsync({ key: rule.cle, valeur: changed, motif: motif.trim() });
      onOpenChange(false);
    } catch (e) {
      if (!isApiError(e)) {
        setError(fr.errors.generic);
        return;
      }
      setError(e.detail);
      setFieldErrors(
        Object.fromEntries(Object.entries(e.errors).map(([k, v]) => [k, v.join(" ")])),
      );
    }
  }

  return (
    <Dialog open onOpenChange={(open) => !update.isPending && onOpenChange(open)}>
      <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>{t.rules.dialogTitle(rule.libelle)}</DialogTitle>
          <DialogDescription>{rule.description}</DialogDescription>
        </DialogHeader>
        <form
          className="grid gap-4"
          noValidate
          onSubmit={(e) => {
            e.preventDefault();
            void submit();
          }}
        >
          {Object.keys(current).map((field) => (
            <FieldControl
              key={field}
              rule={rule.cle}
              field={field}
              value={draft[field]}
              error={fieldErrors[field]}
              onChange={(next) => setDraft((d) => ({ ...d, [field]: next }))}
            />
          ))}
          {weakening && (
            <p role="status" className="rounded-md border border-warning/50 p-3 text-sm">
              {t.rules.weakeningNotice}
            </p>
          )}
          <div className="grid gap-1.5">
            <Label htmlFor={id}>{t.rules.reasonLabel}</Label>
            <Textarea
              id={id}
              rows={3}
              value={motif}
              maxLength={1000}
              aria-describedby={`${id}-help`}
              aria-invalid={fieldErrors.motif !== undefined}
              onChange={(e) => setMotif(e.target.value)}
            />
            <p id={`${id}-help`} className="text-xs text-text-muted">
              {t.rules.reasonHelp}
            </p>
            {fieldErrors.motif && <p className="text-sm text-destructive">{fieldErrors.motif}</p>}
          </div>
          {error && (
            <p role="alert" className={ALERT_CLASS}>
              {error}
            </p>
          )}
          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              disabled={update.isPending}
              onClick={() => onOpenChange(false)}
            >
              {fr.common.cancel}
            </Button>
            <Button type="submit" disabled={update.isPending}>
              {t.rules.save}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
