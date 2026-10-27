import { Briefcase } from "lucide-react";
import { EmptyState } from "@/components/EmptyState";
import { fr } from "@/i18n/fr";
import { cn } from "@/lib/utils";
import { MILESTONES, PHASES } from "../phases";
import { PageHeader, PreviewCard, PreviewSection, SkeletonTable, StatStrip } from "./preview";

const d = fr.dashboard;

export function DashboardAuditeur() {
  return (
    <>
      <PageHeader title={d.auditeurTitle} userRole="AUDITEUR" />
      <EmptyState
        title={d.emptyTitle}
        description={d.auditeurText}
        action={{
          label: d.auditeurAction,
          icon: Briefcase,
          note: `${d.availableAtLot} ${d.auditeurLot}`,
        }}
      />
      <PreviewSection>
        <div className="col-span-12">
          <StatStrip
            items={[
              { label: d.stepsInProgress, foot: d.allMissions },
              { label: d.deliverables, foot: d.thisWeek },
              { label: d.awaitingValidation, foot: d.submittedToRai },
            ]}
          />
        </div>
        <PreviewCard title={d.myStepsInProgress} meta={d.ifaciSteps} span={12}>
          <div className="grid gap-6 border-b border-border p-5 md:grid-cols-[10fr_4fr_4fr]">
            {PHASES.map((phase) => (
              <div key={phase.name}>
                <p className="text-sm font-semibold">
                  {phase.name}{" "}
                  <span className="text-xs font-normal text-text-muted">{phase.range}</span>
                </p>
                <ol className="mt-3 flex gap-[3px]">
                  {phase.steps.map((step) => (
                    <li
                      key={step}
                      className={cn(
                        "flex h-6 flex-1 items-center justify-center border border-border bg-surface text-[10px] text-text-muted tabular-nums",
                        MILESTONES.includes(step) ? "rounded-[2px] font-semibold" : "rounded-full",
                      )}
                    >
                      {step}
                    </li>
                  ))}
                </ol>
              </div>
            ))}
          </div>
          <p className="px-5 py-2 text-xs text-text-muted">◆ {d.milestoneLegend}</p>
          <SkeletonTable
            columns={[
              { label: d.colMission, width: 90 },
              { label: d.colStep, width: 60 },
              { label: d.colPhase, width: 90 },
              { label: d.colDeliverable, width: 160 },
              { label: d.colDueDate, width: 72 },
            ]}
          />
        </PreviewCard>
      </PreviewSection>
    </>
  );
}
