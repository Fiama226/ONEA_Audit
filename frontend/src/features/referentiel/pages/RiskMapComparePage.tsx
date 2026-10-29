import { useState } from "react";
import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { fr } from "@/i18n/fr";
import { useRiskMap, useRiskMapComparison, useRiskMaps } from "../api";
import { NativeSelect } from "@/components/form/NativeSelect";
import { NIVEAU_LABELS, PRIORITE_LABELS, REPONSE_LABELS } from "../labels";
import type { Comparaison } from "../types";

const c = fr.refCartographie;

const FIELD_LABELS: Record<string, string> = {
  libelle: c.colRisque,
  description: c.fieldDescription,
  processus: c.colProcessus,
  objet_auditable: c.fieldObjet,
  probabilite: fr.referentiel.probabilite,
  impact: fr.referentiel.impact,
  score: fr.referentiel.score,
  niveau: fr.referentiel.niveau,
  vulnerabilite: fr.referentiel.vulnerabilite,
  reponse: fr.referentiel.reponse,
  priorite: fr.referentiel.priorite,
  objectif_controle: fr.referentiel.objectifControle,
  dispositif_controle: fr.referentiel.dispositifControle,
};

function displayValue(field: string, value: string | null): string {
  if (value === null || value === "") return c.noValue;
  if (field === "niveau") return NIVEAU_LABELS[value as keyof typeof NIVEAU_LABELS] ?? value;
  if (field === "reponse") return REPONSE_LABELS[value as keyof typeof REPONSE_LABELS] ?? value;
  if (field === "priorite") return PRIORITE_LABELS[Number(value) as 1 | 2 | 3] ?? value;
  return value;
}

function RiskList({ title, items }: { title: string; items: Comparaison["ajoutes"] }) {
  if (items.length === 0) return null;
  return (
    <section className="grid gap-2">
      <h3 className="text-base font-semibold">{`${title} (${items.length})`}</h3>
      <ul className="divide-y divide-border rounded-lg border border-border bg-surface">
        {items.map((r) => (
          <li key={r.id} className="flex items-center gap-4 px-4 py-2 text-sm">
            <span className="font-medium tabular-nums">{r.code}</span>
            <span className="flex-1">{r.libelle}</span>
            <span className="tabular-nums text-text-muted">{r.score}</span>
          </li>
        ))}
      </ul>
    </section>
  );
}

export function RiskMapComparePage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const avec = params.get("avec") ?? "";
  const [choice, setChoice] = useState(avec);
  const current = useRiskMap(id);
  const other = useRiskMap(avec || undefined);
  const maps = useRiskMaps({ page_size: 100, ordering: "-annee" });

  // Le serveur prend la version de l'URL comme référence : on met toujours la plus ancienne
  // (par année) en référence et la plus récente en cible, quel que soit le sens de navigation.
  let reference: string | undefined;
  let target: string | undefined;
  if (current.data && other.data) {
    const currentIsOlder =
      current.data.annee !== other.data.annee
        ? current.data.annee < other.data.annee
        : current.data.created_at <= other.data.created_at;
    reference = (currentIsOlder ? current.data : other.data).id;
    target = (currentIsOlder ? other.data : current.data).id;
  }
  const comparison = useRiskMapComparison(reference, target);
  const others = (maps.data?.results ?? []).filter((v) => v.id !== id);
  const data = comparison.data;
  const empty =
    data && data.ajoutes.length === 0 && data.retires.length === 0 && data.modifies.length === 0;
  const failed = Boolean(avec) && (comparison.isError || other.isError);
  const loading = Boolean(avec) && !failed && !data;

  return (
    <div className="grid gap-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <h2 className="text-xl font-semibold">{c.compareTitle}</h2>
        <form
          className="flex items-end gap-2 print:hidden"
          onSubmit={(e) => {
            e.preventDefault();
            void navigate(
              choice
                ? `/referentiel/cartographies/${id}/comparer?avec=${choice}`
                : `/referentiel/cartographies/${id}/comparer`,
            );
          }}
        >
          <div className="grid gap-1.5">
            <Label htmlFor="compare-version">{c.compareSelector}</Label>
            <NativeSelect
              id="compare-version"
              value={choice}
              onChange={(e) => setChoice(e.target.value)}
            >
              <option value="">{c.compareChoose}</option>
              {others.map((v) => (
                <option key={v.id} value={v.id}>
                  {v.libelle}
                </option>
              ))}
            </NativeSelect>
          </div>
          <Button type="submit" variant="outline" disabled={!choice}>
            {c.compareButton}
          </Button>
        </form>
      </div>
      <Link
        to={`/referentiel/cartographies/${id}`}
        className="text-sm text-primary underline-offset-4 hover:underline print:hidden"
      >
        {c.backToMap}
      </Link>

      {!avec && <p className="text-sm text-text-muted">{c.comparePick}</p>}
      {loading && <Skeleton className="h-32 w-full" />}
      {failed && (
        <p role="alert" className="text-sm text-destructive">
          {c.compareError}
        </p>
      )}
      {data && (
        <>
          <p className="text-sm text-text-muted">
            {c.compareRange
              .replace("{a}", data.reference.libelle)
              .replace("{b}", data.cible.libelle)}
          </p>
          {empty ? (
            <p className="rounded-lg border border-border bg-surface p-6 text-sm">
              {c.compareNone}
            </p>
          ) : (
            <>
              <RiskList title={c.compareAdded} items={data.ajoutes} />
              <RiskList title={c.compareRemoved} items={data.retires} />
              {data.modifies.length > 0 && (
                <section className="grid gap-2">
                  <h3 className="text-base font-semibold">{`${c.compareModified} (${data.modifies.length})`}</h3>
                  {data.modifies.map((m) => (
                    <div
                      key={m.code}
                      className="overflow-hidden rounded-lg border border-border bg-surface"
                    >
                      <table className="w-full text-sm">
                        <caption className="border-b border-border bg-surface-subtle px-4 py-2 text-left font-medium">
                          {m.code}
                        </caption>
                        <thead>
                          <tr className="text-left text-xs text-text-muted">
                            <th scope="col" className="px-4 py-2 font-semibold">
                              {c.compareField}
                            </th>
                            <th scope="col" className="px-4 py-2 font-semibold">
                              {`${c.compareBefore} (${data.reference.annee})`}
                            </th>
                            <th scope="col" className="px-4 py-2 font-semibold">
                              {`${c.compareAfter} (${data.cible.annee})`}
                            </th>
                          </tr>
                        </thead>
                        <tbody>
                          {Object.entries(m.changements).map(([field, [before, after]]) => (
                            <tr key={field} className="border-t border-border align-top">
                              <th scope="row" className="px-4 py-2 text-left font-normal">
                                {FIELD_LABELS[field] ?? field}
                              </th>
                              <td className="px-4 py-2">{displayValue(field, before ?? null)}</td>
                              <td className="px-4 py-2">{displayValue(field, after ?? null)}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  ))}
                </section>
              )}
            </>
          )}
        </>
      )}
    </div>
  );
}
