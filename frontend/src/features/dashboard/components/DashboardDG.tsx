import { FileText } from "lucide-react";
import { EmptyState } from "@/components/EmptyState";
import { fr } from "@/i18n/fr";
import { PageHeader, PreviewCard, PreviewSection, SkeletonTable, StatStrip } from "./preview";

const d = fr.dashboard;

const SEGMENTS: { label: string; className: string }[] = [
  { label: d.statusDone, className: "bg-success/[0.32]" },
  { label: d.statusInProgress, className: "bg-warning/[0.32]" },
  { label: d.statusNotStarted, className: "bg-border" },
  { label: d.statusLate, className: "bg-danger/[0.32]" },
];

export function DashboardDG() {
  return (
    <>
      <PageHeader title={d.dgTitle} userRole="DG" />
      <EmptyState
        title={d.emptyTitle}
        description={d.dgText}
        action={{ label: d.dgAction, icon: FileText, note: `${d.availableAtLot} ${d.dgLot}` }}
      />
      <PreviewSection>
        <div className="col-span-12">
          <StatStrip
            items={[
              { label: d.reportsPublished, foot: `${d.programme} 2026` },
              { label: d.recommendationsIssued, foot: d.allEntities },
              { label: d.recommendationsLate, foot: d.overdue },
            ]}
          />
        </div>
        <PreviewCard
          title={d.implementationRate}
          meta={d.recommendationsMeta}
          span={5}
          bodyClassName="p-5"
        >
          <p className="text-[32px] leading-none font-semibold text-text-muted tabular-nums">
            {d.placeholderValue}
            <span className="ml-1 text-base">%</span>
          </p>
          <p className="mt-2 text-xs text-text-muted">{d.rateNote}</p>
          <div className="mt-4 flex h-2 gap-[3px]">
            {SEGMENTS.map((s) => (
              <span key={s.label} className={`flex-1 rounded-[2px] ${s.className}`} />
            ))}
          </div>
          <ul className="mt-3 flex flex-wrap gap-x-4 gap-y-1 text-xs text-text-muted">
            {SEGMENTS.map((s) => (
              <li key={s.label} className="flex items-center gap-1.5">
                <span className={`size-2 rounded-full ${s.className}`} />
                {s.label}
              </li>
            ))}
          </ul>
        </PreviewCard>
        <PreviewCard title={d.latestReports} meta={d.validatedReports} span={7}>
          <SkeletonTable
            columns={[
              { label: d.colReport, width: 150 },
              { label: d.colAuditedEntity, width: 100 },
              { label: d.colPublishedOn, width: 72 },
              { label: d.colRecommendations, width: 28, numeric: true },
            ]}
          />
        </PreviewCard>
      </PreviewSection>
    </>
  );
}
