import { Printer } from "lucide-react";
import { useState } from "react";
import { useSearchParams } from "react-router-dom";
import { PrintLayout } from "@/components/print/PrintLayout";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { ALERT_CLASS } from "@/components/form/FormField";
import { useAuth } from "@/auth/useAuth";
import { fr } from "@/i18n/fr";
import { downloadFollowUpExport, useFollowUpActions, useFollowUpRecommendations } from "../api";
import { ActionsTable } from "../components/ActionsTable";
import {
  EMPTY_FILTERS,
  RegisterFilters,
  type FilterValues,
  type RegisterView,
} from "../components/RegisterFilters";
import { RecommendationsTable } from "../components/RecommendationsTable";
import type {
  ActionParams,
  FormatExport,
  PrioriteRecommandation,
  RecommendationParams,
  StatutRecommandationSuivi,
  StatutSuivi,
} from "../types";

const t = fr.suiviRegistre;
const PAGE_SIZE = 25;
const FILTER_KEYS = Object.keys(EMPTY_FILTERS) as (keyof FilterValues)[];

function readFilters(search: URLSearchParams): FilterValues {
  return {
    annee: search.get("annee") ?? "",
    mission: search.get("mission") ?? "",
    entite: search.get("entite") ?? "",
    priorite: search.get("priorite") ?? "",
    statut: search.get("statut") ?? "",
    en_retard: search.get("en_retard") === "true",
    mine: search.get("mine") === "true",
  };
}

function annee(values: FilterValues): number | undefined {
  const n = Number(values.annee);
  return values.annee !== "" && Number.isInteger(n) ? n : undefined;
}

/** Paramètres d'API des actions (le filtre « priorité » ne s'applique qu'aux recommandations). */
function actionParams(values: FilterValues, ordering: string, mine: boolean): ActionParams {
  return {
    annee: annee(values),
    mission: values.mission || undefined,
    entite: values.entite || undefined,
    statut: values.statut ? [values.statut as StatutSuivi] : undefined,
    en_retard: values.en_retard || undefined,
    mine: mine && values.mine ? true : undefined,
    ordering: ordering || undefined,
  };
}

function recommendationParams(values: FilterValues, ordering: string): RecommendationParams {
  return {
    annee: annee(values),
    mission: values.mission || undefined,
    entite: values.entite || undefined,
    priorite: (values.priorite || undefined) as PrioriteRecommandation | undefined,
    statut_suivi: values.statut ? [values.statut as StatutRecommandationSuivi] : undefined,
    en_retard: values.en_retard || undefined,
    ordering: ordering || undefined,
  };
}

/** Registre des recommandations et des actions : filtres conservés dans l'URL (paramètre `vue`). */
export function RegisterPage() {
  const { me } = useAuth();
  const role = me?.role ?? "AUDITE";
  const [search, setSearch] = useSearchParams();
  const view: RegisterView = search.get("vue") === "actions" ? "actions" : "recommandations";
  const values = readFilters(search);
  const ordering = search.get("tri") ?? "";
  const page = Math.max(1, Number(search.get("page")) || 1);
  const [exportError, setExportError] = useState(false);

  const isAudite = role === "AUDITE";
  const actionQuery = actionParams(values, view === "actions" ? ordering : "", isAudite);
  const recoQuery = recommendationParams(values, view === "recommandations" ? ordering : "");
  const actions = useFollowUpActions(actionQuery);
  const recommendations = useFollowUpRecommendations(recoQuery);
  const current = view === "actions" ? actions : recommendations;

  function update(patch: Record<string, string | undefined>) {
    setSearch(
      (previous) => {
        const next = new URLSearchParams(previous);
        for (const [key, value] of Object.entries(patch)) {
          if (value === undefined || value === "") next.delete(key);
          else next.set(key, value);
        }
        return next;
      },
      { replace: true },
    );
  }

  function changeFilters(patch: Partial<FilterValues>) {
    const flat: Record<string, string | undefined> = { page: undefined };
    for (const [key, value] of Object.entries(patch)) {
      flat[key] = typeof value === "boolean" ? (value ? "true" : undefined) : value;
    }
    update(flat);
  }

  function changeView(next: string) {
    // Les statuts et la priorité n'ont pas le même sens d'une vue à l'autre.
    update({
      vue: next === "actions" ? "actions" : undefined,
      statut: undefined,
      priorite: undefined,
      tri: undefined,
      page: undefined,
      mine: undefined,
    });
  }

  function reset() {
    update(Object.fromEntries([...FILTER_KEYS.map((k) => [k, undefined]), ["page", undefined]]));
  }

  async function exportAs(format: FormatExport) {
    setExportError(false);
    try {
      if (view === "actions") await downloadFollowUpExport("actions", actionQuery, format);
      else await downloadFollowUpExport("recommendations", recoQuery, format);
    } catch {
      setExportError(true);
    }
  }

  const total = current.data?.count ?? 0;
  const pageRows = <T,>(rows: T[]) => rows.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE);
  const loadFailed = current.isError && current.data === undefined;

  return (
    <PrintLayout title={fr.suivi.registerTitle} orientation="paysage">
      <h1 className="mb-6 text-2xl font-semibold tracking-[-0.012em] print:hidden">
        {fr.suivi.registerTitle}
      </h1>
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3 print:hidden">
        <nav aria-label={t.viewsLabel}>
          <ul className="flex gap-4 border-b border-border">
            {(
              [
                ["recommandations", t.tabRecommendations],
                ["actions", t.tabActions],
              ] as const
            ).map(([value, label]) => (
              <li key={value}>
                <button
                  type="button"
                  aria-current={view === value ? "page" : undefined}
                  onClick={() => changeView(value)}
                  className={cn(
                    "inline-block border-b-2 px-1 pb-2 text-sm font-medium",
                    view === value
                      ? "border-primary text-primary"
                      : "border-transparent text-text-muted hover:text-foreground",
                  )}
                >
                  {label}
                </button>
              </li>
            ))}
          </ul>
        </nav>{" "}
        <div className="flex items-center gap-2">
          <div role="group" aria-label={t.export} className="flex items-center gap-1">
            <span className="mr-1 text-sm text-text-muted" aria-hidden>
              {t.export} :
            </span>
            <Button type="button" variant="outline" size="sm" onClick={() => void exportAs("csv")}>
              {t.exportCsv}
            </Button>
            <Button type="button" variant="outline" size="sm" onClick={() => void exportAs("xlsx")}>
              {t.exportXlsx}
            </Button>
          </div>
          <Button type="button" variant="outline" size="sm" onClick={() => window.print()}>
            <Printer aria-hidden />
            {t.print}
          </Button>
        </div>
      </div>
      <div className="mb-4">
        <RegisterFilters
          view={view}
          role={role}
          values={values}
          onChange={changeFilters}
          onReset={reset}
        />
      </div>
      {exportError && (
        <p role="alert" className={`${ALERT_CLASS} mb-4`}>
          {t.exportError}
        </p>
      )}
      {loadFailed ? (
        <p role="alert" className={ALERT_CLASS}>
          {t.loadError}
        </p>
      ) : view === "actions" ? (
        <ActionsTable
          actions={pageRows(actions.data?.results ?? [])}
          total={total}
          page={page}
          pageSize={PAGE_SIZE}
          onPageChange={(p) => update({ page: p > 1 ? String(p) : undefined })}
          ordering={ordering}
          onOrderingChange={(o) => update({ tri: o, page: undefined })}
          isLoading={current.isLoading}
        />
      ) : (
        <RecommendationsTable
          recommendations={pageRows(recommendations.data?.results ?? [])}
          total={total}
          page={page}
          pageSize={PAGE_SIZE}
          onPageChange={(p) => update({ page: p > 1 ? String(p) : undefined })}
          ordering={ordering}
          onOrderingChange={(o) => update({ tri: o, page: undefined })}
          isLoading={current.isLoading}
        />
      )}
    </PrintLayout>
  );
}
