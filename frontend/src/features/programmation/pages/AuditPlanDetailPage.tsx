import { Pencil, Plus, Printer, Trash2, X } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { Link, useLocation, useNavigate, useParams, useSearchParams } from "react-router-dom";
import { isApiError } from "@/api/errors";
import { useRole } from "@/auth/useRole";
import { Button } from "@/components/ui/button";
import { PrintLayout } from "@/components/print/PrintLayout";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { fr } from "@/i18n/fr";
import { useAuditPlan, useAuditPlanLines } from "../api";
import { AuditPlanCalendar } from "../components/AuditPlanCalendar";
import { DeletePlanDialog } from "../components/DeletePlanDialog";
import { EditPlanDialog } from "../components/EditPlanDialog";
import { PlanApprovalPanel } from "../components/PlanApprovalPanel";
import { PlanExportButtons } from "../components/PlanExportButtons";
import { PlanFilters, type PlanFilterValues } from "../components/PlanFilters";
import { PlanFrozenBanner } from "../components/PlanFrozenBanner";
import { PlanLinesTable } from "../components/PlanLinesTable";
import { PlanStatusBadge } from "../components/PlanStatusBadge";
import { PlanSummary } from "../components/PlanSummary";
import { ValidatePlanDialog } from "../components/ValidatePlanDialog";
import { canEditAuditPlan } from "../permissions";
import { ListIncompleteAlert, useAllProcesses } from "../shared";

const p = fr.programmation;
const c = fr.programmationPlans;

export function AuditPlanDetailPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { role } = useRole();
  const [params, setParams] = useSearchParams();
  const [validating, setValidating] = useState(false);
  const [editing, setEditing] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const titleRef = useRef<HTMLHeadingElement>(null);
  const [deleted, setDeleted] = useState(false);
  // Message transmis par le formulaire de mission (état de navigation) : lu une fois, puis retiré.
  const location = useLocation();
  const [flash, setFlash] = useState<string | null>(() => {
    const state = location.state as { flash?: unknown } | null;
    return typeof state?.flash === "string" ? state.flash : null;
  });
  useEffect(() => {
    if ((location.state as { flash?: unknown } | null)?.flash !== undefined) {
      void navigate(
        { pathname: location.pathname, search: location.search },
        { replace: true, state: null },
      );
    }
  }, [location, navigate]);

  const plan = useAuditPlan(deleted ? undefined : id);
  const lines = useAuditPlanLines(deleted ? undefined : id);
  const processes = useAllProcesses();

  const view = params.get("vue") === "calendrier" ? "calendrier" : "liste";
  const filters: PlanFilterValues = {
    processus: params.get("processus") ?? "",
    type: params.get("type") ?? "",
    trimestre: params.get("trimestre") ?? "",
    q: params.get("q") ?? "",
  };

  function update(changes: Record<string, string | null>) {
    setParams(
      (prev) => {
        const next = new URLSearchParams(prev);
        for (const [key, value] of Object.entries(changes)) {
          if (value) next.set(key, value);
          else next.delete(key);
        }
        return next;
      },
      { replace: true },
    );
  }

  if (deleted) return null;
  if (plan.isLoading) {
    return (
      <div role="status" aria-busy="true" aria-label={fr.common.loading} className="grid gap-4">
        <Skeleton className="h-8 w-80" />
        <Skeleton className="h-64 w-full" />
      </div>
    );
  }
  if (plan.isError || !plan.data || !id) {
    const notFound = isApiError(plan.error) && plan.error.status === 404;
    return (
      <div role="alert" className="rounded-lg border border-border bg-surface p-6 text-sm">
        <p>{notFound ? c.notFound : fr.errors.generic}</p>
        <Link to="/programme-annuel" className="mt-3 inline-block text-primary underline">
          {c.backToList}
        </Link>
      </div>
    );
  }

  const data = plan.data;
  const frozen = data.statut === "VALIDE";
  const canEdit = canEditAuditPlan(role) && !frozen;
  const all = lines.data?.results ?? [];
  const needle = filters.q.trim().toLocaleLowerCase("fr");
  const shown = all.filter(
    (l) =>
      (!filters.processus || l.processus === filters.processus) &&
      (!filters.type || l.type === filters.type) &&
      (!filters.trimestre || String(l.trimestre) === filters.trimestre) &&
      (!needle || l.titre.toLocaleLowerCase("fr").includes(needle)),
  );
  const filteredOut = all.length > 0 && shown.length !== all.length;
  const noProcess = processes.data !== undefined && processes.data.results.length === 0;
  const addLine = (
    <Button type="button" onClick={() => void navigate(`/programme-annuel/${id}/nouvelle-ligne`)}>
      <Plus aria-hidden />
      {c.addLine}
    </Button>
  );

  let linesBody;
  if (lines.isError) {
    linesBody = (
      <div role="alert" className="rounded-lg border border-border bg-surface p-4 text-sm">
        <p>{c.linesLoadError}</p>
        <Button
          type="button"
          variant="outline"
          className="mt-3"
          onClick={() => void lines.refetch()}
        >
          {fr.common.retry}
        </Button>
      </div>
    );
  } else if (lines.isLoading) {
    linesBody = <Skeleton className="h-40 w-full" aria-label={fr.common.loading} />;
  } else if (all.length === 0) {
    linesBody = (
      <div className="grid gap-3 rounded-lg border border-border bg-surface p-6 text-sm">
        {canEdit && noProcess ? (
          <>
            <p>{c.noProcess}</p>
            <Link to="/referentiel/processus" className="text-primary underline">
              {c.noProcessLink}
            </Link>
          </>
        ) : (
          <>
            <p className="text-text-muted">{canEdit ? c.emptyLinesRai : c.emptyLinesOther}</p>
            {canEdit && <div>{addLine}</div>}
          </>
        )}
      </div>
    );
  } else if (shown.length === 0) {
    linesBody = (
      <div className="grid gap-3 rounded-lg border border-border bg-surface p-6 text-sm">
        <p className="text-text-muted">{c.emptyFiltered}</p>
        <div>
          <Button
            type="button"
            variant="outline"
            onClick={() => update({ processus: null, type: null, trimestre: null, q: null })}
          >
            {c.clearFilters}
          </Button>
        </div>
      </div>
    );
  } else {
    linesBody = <PlanLinesTable lines={shown} />;
  }

  return (
    <PrintLayout title={`${p.title} ${data.annee}`} orientation="paysage">
      <div className="grid gap-6">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="grid gap-2">
            <div className="flex flex-wrap items-center gap-3">
              <h1
                ref={titleRef}
                tabIndex={-1}
                className="text-2xl font-semibold outline-none print:hidden"
              >
                {`${p.title} ${data.annee}`}
              </h1>
              <PlanStatusBadge statut={data.statut} />
            </div>
            <p className="text-sm text-text-muted">{data.libelle}</p>
            {data.commentaire && <p className="max-w-[70ch] text-sm">{data.commentaire}</p>}
          </div>
          <div className="flex flex-wrap items-start gap-3 print:hidden">
            {canEdit && (
              <>
                {!noProcess && addLine}
                <Button type="button" variant="outline" onClick={() => setEditing(true)}>
                  <Pencil aria-hidden />
                  {c.editAction}
                </Button>
                <Button type="button" variant="outline" onClick={() => setValidating(true)}>
                  {c.validateAction}
                </Button>
                <Button type="button" variant="outline" onClick={() => setDeleting(true)}>
                  <Trash2 aria-hidden />
                  {c.deleteAction}
                </Button>
              </>
            )}
            <PlanExportButtons id={id} />
            <Button type="button" variant="outline" onClick={() => window.print()}>
              <Printer aria-hidden />
              {p.print}
            </Button>
          </div>
        </div>

        {flash && (
          <p
            role="status"
            className="flex items-center justify-between gap-3 rounded-md border border-border bg-surface-subtle px-4 py-2 text-sm print:hidden"
          >
            <span>{flash}</span>
            <Button
              type="button"
              variant="ghost"
              size="icon"
              aria-label={c.dismissFlash}
              onClick={() => setFlash(null)}
            >
              <X aria-hidden />
            </Button>
          </p>
        )}

        {frozen && <PlanFrozenBanner plan={data} />}
        <PlanApprovalPanel plan={data} />

        <PlanSummary planId={id} />

        <section aria-labelledby="plan-lines-title" className="grid gap-3">
          <h2 id="plan-lines-title" className="text-base font-semibold">
            {c.linesTitle}
          </h2>
          <Tabs value={view} onValueChange={(v) => update({ vue: v === "liste" ? null : v })}>
            <TabsList aria-label={c.viewsLabel} className="print:hidden">
              <TabsTrigger value="liste">{c.viewList}</TabsTrigger>
              <TabsTrigger value="calendrier">{c.viewCalendar}</TabsTrigger>
            </TabsList>
            {/* Les deux vues restent montées : à l'impression, elles sortent l'une après l'autre. */}
            <TabsContent
              value="liste"
              forceMount
              className="grid gap-3 data-[state=inactive]:hidden print:data-[state=inactive]:grid"
            >
              <PlanFilters
                values={filters}
                processes={processes.data?.results ?? []}
                onChange={(next) => update(next)}
              />
              {lines.data && <ListIncompleteAlert loaded={all.length} count={lines.data.count} />}
              {/* Les filtres sont masqués à l'impression : le papier porte donc toujours le tableau
                complet, à côté du calendrier complet. */}
              <div className={filteredOut ? "print:hidden" : undefined}>{linesBody}</div>
              {filteredOut && (
                <div data-print-full aria-hidden="true" className="hidden print:block">
                  <PlanLinesTable lines={all} />
                </div>
              )}
            </TabsContent>
            <TabsContent
              value="calendrier"
              forceMount
              className="data-[state=inactive]:hidden print:data-[state=inactive]:block"
            >
              <AuditPlanCalendar year={data.annee} lines={all} />
            </TabsContent>
          </Tabs>
        </section>

        {canEditAuditPlan(role) && (
          <ValidatePlanDialog
            id={id}
            open={validating}
            onOpenChange={setValidating}
            onValidated={() => titleRef.current?.focus()}
          />
        )}
        {canEdit && <EditPlanDialog plan={data} open={editing} onOpenChange={setEditing} />}
        {canEdit && (
          <DeletePlanDialog
            id={id}
            open={deleting}
            onOpenChange={setDeleting}
            onDeleted={() => setDeleted(true)}
          />
        )}
      </div>
    </PrintLayout>
  );
}
