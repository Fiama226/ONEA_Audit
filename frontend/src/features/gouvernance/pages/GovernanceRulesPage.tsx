import { AlertTriangle, Pencil } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";
import { useAuth } from "@/auth/useAuth";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { fr } from "@/i18n/fr";
import { formatDateTime } from "@/lib/dates";
import { useGovernanceRules, type GovernanceRule } from "../api";
import { RuleEditDialog } from "../components/RuleEditDialog";
import { fieldLabel, formatValue, t } from "../textes";

type Value = Record<string, unknown>;

/** Avertissement permanent tant qu'une règle est assouplie (celles issues des normes d'abord). */
export function RelaxedWarnings({ rules }: { rules: GovernanceRule[] }) {
  const relaxed = rules
    .filter((r) => r.assouplie)
    .sort((a, b) => Number(b.issue_des_normes) - Number(a.issue_des_normes));
  if (relaxed.length === 0) return null;
  return (
    <section
      aria-labelledby="relaxed-title"
      className="rounded-lg border border-warning/60 bg-surface p-4"
    >
      <h2 id="relaxed-title" className="mb-2 flex items-center gap-2 text-base font-semibold">
        <AlertTriangle className="size-4 shrink-0 text-warning-text" aria-hidden />
        {t.rules.relaxedTitle}
      </h2>
      <ul className="m-0 grid list-none gap-1 p-0 text-sm">
        {relaxed.map((r) => (
          <li key={r.cle}>
            {r.issue_des_normes
              ? t.rules.relaxedNormWarning(r.libelle)
              : t.rules.relaxedOther(r.libelle)}
            {r.motif && (
              <span className="text-text-muted">{` (${t.rules.reasonOf.toLowerCase()} : ${r.motif})`}</span>
            )}
          </li>
        ))}
      </ul>
    </section>
  );
}

function RuleCard({
  rule,
  canEdit,
  onEdit,
}: {
  rule: GovernanceRule;
  canEdit: boolean;
  onEdit: () => void;
}) {
  const valeur = rule.valeur as Value;
  const defaut = rule.defaut as Value;
  const headingId = `rule-${rule.cle}`;
  return (
    <section
      aria-labelledby={headingId}
      className="grid gap-3 rounded-lg border border-border bg-surface p-4"
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="grid gap-1">
          <h2 id={headingId} className="flex flex-wrap items-center gap-2 text-base font-semibold">
            {rule.libelle}
            {rule.issue_des_normes && <Badge variant="secondary">{t.rules.normBadge}</Badge>}
            {rule.assouplie && (
              <Badge variant="outline" className="border-warning text-warning-text">
                {t.rules.relaxedBadge}
              </Badge>
            )}
          </h2>
          <p className="max-w-[75ch] text-sm text-text-muted">{rule.description}</p>
          <p className="text-xs text-text-muted">{`${t.rules.reference} : ${rule.reference}`}</p>
        </div>
        {canEdit && (
          <Button
            type="button"
            variant="outline"
            size="sm"
            aria-label={`${t.rules.edit} : ${rule.libelle}`}
            onClick={onEdit}
          >
            <Pencil aria-hidden />
            {t.rules.edit}
          </Button>
        )}
      </div>
      <dl className="grid gap-x-6 gap-y-2 text-sm sm:grid-cols-[minmax(0,1fr)_auto]">
        {Object.keys(valeur).map((field) => {
          const differs = valeur[field] !== defaut[field];
          return (
            <div key={field} className="contents">
              <dt className="text-text-muted">{fieldLabel(rule.cle, field)}</dt>
              <dd className="m-0 font-medium">
                {formatValue(rule.cle, field, valeur[field])}
                {differs && (
                  <span className="block text-xs font-normal text-text-muted">
                    {`${t.rules.defaultValue} : ${formatValue(rule.cle, field, defaut[field])}`}
                  </span>
                )}
              </dd>
            </div>
          );
        })}
      </dl>
      <p className="text-xs text-text-muted">
        {rule.modifie_le && rule.modifie_par
          ? t.rules.lastChange(rule.modifie_par.nom_complet, formatDateTime(rule.modifie_le))
          : t.rules.neverChanged}
        {rule.motif ? ` · ${t.rules.reasonOf} : ${rule.motif}` : ""}
      </p>
    </section>
  );
}

export function GovernanceRulesPage() {
  const query = useGovernanceRules();
  const { me } = useAuth();
  const isAdmin = me?.role === "ADMIN";
  const [editing, setEditing] = useState<GovernanceRule | null>(null);

  let body;
  if (query.isError) {
    body = (
      <div role="alert" className="rounded-lg border border-border bg-surface p-6 text-sm">
        <p>{t.rules.loadError}</p>
        <Button
          type="button"
          variant="outline"
          className="mt-3"
          onClick={() => void query.refetch()}
        >
          {fr.common.retry}
        </Button>
      </div>
    );
  } else if (!query.data) {
    body = (
      <div role="status" aria-label={fr.common.loading} className="grid gap-4">
        <Skeleton className="h-28 w-full" />
        <Skeleton className="h-28 w-full" />
      </div>
    );
  } else {
    body = (
      <>
        <RelaxedWarnings rules={query.data} />
        {query.data.map((rule) => (
          <RuleCard key={rule.cle} rule={rule} canEdit={isAdmin} onEdit={() => setEditing(rule)} />
        ))}
      </>
    );
  }

  return (
    <div className="grid max-w-5xl gap-4">
      <div>
        <h1 className="text-2xl font-semibold">{t.rules.title}</h1>
        <p className="mt-1 max-w-[75ch] text-sm text-text-muted">{t.rules.help}</p>
        {!isAdmin && <p className="mt-1 text-sm text-text-muted">{t.rules.readOnly}</p>}
        <Link
          to="/journal-audit?categorie=gouvernance"
          className="mt-2 inline-block text-sm font-medium text-primary underline underline-offset-2"
        >
          {t.rules.journalLink}
        </Link>
      </div>
      {body}
      {editing && (
        <RuleEditDialog rule={editing} onOpenChange={(open) => !open && setEditing(null)} />
      )}
    </div>
  );
}
