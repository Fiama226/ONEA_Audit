import { TriangleAlert } from "lucide-react";
import { useState, type FormEvent } from "react";
import { isApiError } from "@/api/errors";
import { ALERT_CLASS } from "@/components/form/FormField";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { fr } from "@/i18n/fr";
import { formatDateTime } from "@/lib/dates";
import { useDelegation, useSetDelegation } from "../api";
import type { CompteUtilisateur, Delegation, DelegationInput } from "../types";

const t = fr.utilisateurs.delegation;
const RIGHTS = ["creer", "reinitialiser", "roles", "desactiver"] as const;

/**
 * Délégation de la gestion des comptes à un agent non administrateur. Le parent ne la monte
 * que pour un administrateur : un délégué ne lit ni ne modifie aucune délégation.
 */
export function DelegationCard({ account }: { account: CompteUtilisateur }) {
  const query = useDelegation(account.id, true);
  return (
    <Card>
      <CardHeader>
        <CardTitle>{t.title}</CardTitle>
      </CardHeader>
      <CardContent className="grid gap-3 text-sm">
        <p className="text-text-muted">{t.intro}</p>
        <p className="flex gap-2 rounded-md border border-warning/50 p-3 text-warning-text">
          <TriangleAlert className="mt-0.5 size-4 shrink-0" aria-hidden />
          <span>{t.warning}</span>
        </p>
        <p className="text-text-muted">{t.limits}</p>
        {!account.is_active && <p className="font-medium">{t.inactive}</p>}
        {query.isPending && <Skeleton className="h-24 w-full" />}
        {query.isError && (
          <div role="alert" className={ALERT_CLASS}>
            <p>{t.loadError}</p>
            <Button
              type="button"
              variant="outline"
              className="mt-2"
              onClick={() => void query.refetch()}
            >
              {fr.common.retry}
            </Button>
          </div>
        )}
        {query.data && <DelegationForm accountId={account.id} delegation={query.data} />}
      </CardContent>
    </Card>
  );
}

function valuesOf(d: Delegation): DelegationInput {
  return {
    creer: d.creer,
    reinitialiser: d.reinitialiser,
    roles: d.roles,
    desactiver: d.desactiver,
  };
}

function DelegationForm({ accountId, delegation }: { accountId: number; delegation: Delegation }) {
  const mutation = useSetDelegation();
  const [values, setValues] = useState<DelegationInput>(() => valuesOf(delegation));
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);
  const stored = valuesOf(delegation);
  const dirty = RIGHTS.some((r) => values[r] !== stored[r]);

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    setSaved(false);
    try {
      const result = await mutation.mutateAsync({ id: accountId, data: values });
      setValues(valuesOf(result));
      setSaved(true);
    } catch (e) {
      setError(isApiError(e) ? e.detail : fr.errors.generic);
    }
  }

  return (
    <form onSubmit={(e) => void onSubmit(e)} noValidate className="grid gap-3">
      {error && (
        <p role="alert" className={ALERT_CLASS}>
          {error}
        </p>
      )}
      <fieldset className="grid gap-2">
        <legend className="mb-1 font-medium">{t.legend}</legend>
        {RIGHTS.map((right) => (
          <label key={right} className="flex items-center gap-2">
            <input
              type="checkbox"
              className="size-4 accent-primary"
              checked={values[right]}
              disabled={mutation.isPending}
              onChange={(e) => {
                setSaved(false);
                setValues((v) => ({ ...v, [right]: e.target.checked }));
              }}
            />
            {t[right]}
          </label>
        ))}
      </fieldset>
      {delegation.accorde_le && (
        <p className="text-text-muted">
          {`${t.grantedOn}${formatDateTime(delegation.accorde_le)}${
            delegation.accorde_par ? `${t.grantedBy}${delegation.accorde_par.nom_complet}` : ""
          }.`}
        </p>
      )}
      <div className="print:hidden">
        <Button type="submit" variant="outline" disabled={!dirty || mutation.isPending}>
          {mutation.isPending ? t.saving : t.save}
        </Button>
      </div>
      <p role="status" className="text-success-text">
        {saved && !dirty ? t.saved : ""}
      </p>
    </form>
  );
}
