import { ClipboardCheck } from "lucide-react";
import { EmptyState } from "@/components/EmptyState";
import { fr } from "@/i18n/fr";
import { PageHeader, PreviewCard, PreviewSection, SkeletonTable, StatStrip } from "./preview";

const d = fr.dashboard;

export function DashboardAudite() {
  return (
    <>
      <PageHeader title={d.auditeTitle} userRole="AUDITE" />
      <EmptyState
        title={d.emptyTitle}
        description={d.auditeText}
        action={{
          label: d.auditeAction,
          icon: ClipboardCheck,
          note: `${d.availableAtLot} ${d.auditeLot}`,
        }}
      />
      <PreviewSection>
        <div className="col-span-12">
          <StatStrip
            items={[
              { label: d.findingsAddressed, foot: d.submittedForOpinion },
              { label: d.actionsInProgress, foot: d.actionPlan },
              { label: d.actionsDue, foot: d.overdue },
            ]}
          />
        </div>
        <PreviewCard title={d.myFindingsActions} meta={d.entityScope} span={8}>
          <SkeletonTable
            columns={[
              { label: d.colFinding, width: 140 },
              { label: d.colRecommendation, width: 130 },
              { label: d.colAction, width: 110 },
              { label: d.colDueDate, width: 72 },
              { label: d.colFollowUp, width: 80 },
            ]}
          />
        </PreviewCard>
        <PreviewCard title={d.yourRole} span={4} decorative={false}>
          <ol className="flex flex-col gap-4 p-5">
            {[d.roleStep1, d.roleStep2, d.roleStep3].map((text, i) => (
              <li key={text} className="flex gap-3 text-sm">
                <span className="flex size-6 shrink-0 items-center justify-center rounded-full border border-border bg-background text-xs font-semibold tabular-nums">
                  {i + 1}
                </span>
                <span>{text}</span>
              </li>
            ))}
          </ol>
        </PreviewCard>
      </PreviewSection>
    </>
  );
}
