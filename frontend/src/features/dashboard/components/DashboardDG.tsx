import { useState } from "react";
import { AlertTriangle, CheckCircle2, Download } from "lucide-react";
import { Link } from "react-router-dom";
import { RateMeter, StackedBar, StatTile } from "@/components/charts";
import { PrintLayout } from "@/components/print/PrintLayout";
import { Button } from "@/components/ui/button";
import { fr } from "@/i18n/fr";
import { downloadImplementationRates, useDashboardDg, type TableauDg } from "../api";
import { useYearParam } from "../year";
import { DashError, DashLoading, DashSection, toPercent } from "./DashParts";
import { DiffusedReportsTable } from "./DiffusedReportsTable";
import { HighRisksTable } from "./HighRisksTable";
import { PageHeader, PreviewCard, SkeletonTable } from "./preview";
import { YearFilter } from "./YearFilter";

const d = fr.dashboard;
const t = fr.tableauxDirection;

type Rates = Pick<
  TableauDg["taux"],
  "cloturees" | "abandonnees" | "total" | "taux" | "echues" | "cloturees_echues" | "taux_echues"
>;

/** Actions encore à mener : ni clôturées ni abandonnées (même base que le taux du serveur). */
const base = (r: Rates) => r.total - r.abandonnees;

function LoadingDG() {
  return (
    <DashLoading>
      <div aria-hidden="true" className="grid grid-cols-12 items-start gap-6">
        <PreviewCard title={d.implementationRate} span={5} bodyClassName="p-5">
          <SkeletonTable columns={[{ label: d.implementationRate, width: 120 }]} />
        </PreviewCard>
        <PreviewCard title={t.diffusedReports} span={7}>
          <SkeletonTable
            columns={[
              { label: t.colReference, width: 80 },
              { label: t.colTitle, width: 150 },
              { label: t.colActions, width: 28, numeric: true },
            ]}
          />
        </PreviewCard>
      </div>
    </DashLoading>
  );
}

function AttentionPoints({ data }: { data: TableauDg }) {
  const late = Math.max(0, data.taux.echues - data.taux.cloturees_echues);
  const uncovered = data.risques_eleves.non_couverts;
  const items = [
    uncovered > 0 && {
      to: "/referentiel/cartographies",
      label:
        uncovered === 1
          ? t.attentionRisksOne
          : t.attentionRisks.replace("{count}", String(uncovered)),
    },
    late > 0 && {
      to: "/recommandations",
      label: late === 1 ? t.attentionLateOne : t.attentionLate.replace("{count}", String(late)),
    },
  ].filter((item): item is { to: string; label: string } => item !== false);
  return (
    <section
      aria-labelledby="dg-attention"
      className="rounded-lg border border-border bg-surface p-4"
    >
      <h2 id="dg-attention" className="mb-2 text-base font-semibold">
        {t.attentionTitle}
      </h2>
      {items.length === 0 ? (
        <p className="text-sm text-text-muted">{t.attentionNone}</p>
      ) : (
        <ul className="m-0 flex list-none flex-col gap-1.5 p-0 text-sm">
          {items.map((item) => (
            <li key={item.to}>
              <Link to={item.to} className="text-primary underline underline-offset-2">
                {item.label}
              </Link>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

function Content({ data }: { data: TableauDg }) {
  const { taux, taux_par_direction: dirs, risques_eleves: risks } = data;
  return (
    <div className="flex flex-col gap-6">
      <AttentionPoints data={data} />
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <StatTile label={t.tileCovered} value={risks.couverts} icon={CheckCircle2} tone="success" />
        <StatTile
          label={t.tileNotCovered}
          value={risks.non_couverts}
          icon={AlertTriangle}
          tone="danger"
        />
      </div>

      <DashSection title={d.implementationRate}>
        <div className="flex flex-col gap-4">
          <RateMeter
            label={t.overallRate}
            rate={toPercent(taux.taux)}
            numerator={taux.cloturees}
            denominator={base(taux)}
          />
          <RateMeter
            label={t.dueRate}
            rate={toPercent(taux.taux_echues)}
            numerator={taux.cloturees_echues}
            denominator={taux.echues}
          />
        </div>
      </DashSection>

      <DashSection title={t.actionsByDirection}>
        {dirs.length === 0 ? (
          <p className="text-sm text-text-muted">{t.actionsByDirectionEmpty}</p>
        ) : (
          <>
            <StackedBar
              ariaLabel={t.actionsByDirection}
              rows={dirs.map((r) => {
                const late = Math.max(0, r.echues - r.cloturees_echues);
                return {
                  key: r.direction_id,
                  label: `${r.code} — ${r.libelle}`,
                  segments: {
                    done: r.cloturees,
                    open: Math.max(0, base(r) - r.cloturees - late),
                    late,
                  },
                };
              })}
            />
            <h3 className="mt-5 mb-2 text-sm font-semibold">{t.rateByDirection}</h3>
            <ul className="m-0 flex list-none flex-col gap-3 p-0">
              {dirs.map((r) => (
                <li key={r.direction_id}>
                  <RateMeter
                    label={`${r.code} — ${r.libelle}`}
                    rate={toPercent(r.taux)}
                    numerator={r.cloturees}
                    denominator={base(r)}
                  />
                </li>
              ))}
            </ul>
          </>
        )}
      </DashSection>

      <HighRisksTable risks={risks.risques} />
      <DiffusedReportsTable reports={data.rapports_diffuses} />
    </div>
  );
}

export function DashboardDG() {
  const [annee, setAnnee] = useYearParam();
  const query = useDashboardDg(annee);
  const [exporting, setExporting] = useState(false);
  const [exportFailed, setExportFailed] = useState(false);

  async function onExport() {
    setExporting(true);
    setExportFailed(false);
    try {
      await downloadImplementationRates(annee, "xlsx");
    } catch {
      setExportFailed(true);
    } finally {
      setExporting(false);
    }
  }

  return (
    <PrintLayout title={t.printTitleDg}>
      <PageHeader title={d.dgTitle} userRole="DG" annee={annee} />
      <div className="flex flex-wrap items-start justify-between gap-3">
        <YearFilter value={annee} onChange={setAnnee} />
        <Button
          type="button"
          variant="outline"
          size="sm"
          className="print:hidden"
          disabled={exporting}
          onClick={() => void onExport()}
        >
          <Download aria-hidden="true" />
          {exporting ? t.exporting : t.exportRates}
        </Button>
      </div>
      {exportFailed && (
        <p role="alert" className="mb-4 text-sm font-medium text-destructive">
          {t.exportError}
        </p>
      )}
      {query.isPending ? (
        <LoadingDG />
      ) : query.isError ? (
        <DashError onRetry={() => void query.refetch()} />
      ) : (
        <Content data={query.data} />
      )}
    </PrintLayout>
  );
}
