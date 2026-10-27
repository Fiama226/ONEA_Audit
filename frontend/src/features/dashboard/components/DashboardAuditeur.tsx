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
                <ol className="mt-3 flex flex-wrap gap-1">
                  {phase.steps.map((step) => (
                    <li
                      key={step}
                      className="relative flex size-6 items-center justify-center text-[10px] text-text-muted tabular-nums"
                    >
                      <span
                        className={cn(
                          "absolute border border-border bg-surface",
                          MILESTONES.includes(step)
                            ? "size-[17px] rotate-45 rounded-[2px]"
                            : "size-6 rounded-full",
                        )}
                      />
                      <span
                        className={cn("relative", MILESTONES.includes(step) && "font-semibold")}
                      >
                        {step}
                      </span>
                    </li>
                  ))}
                </ol>
              </div>
            ))}
          </div>
          <p className="flex items-center gap-2 px-5 py-2 text-xs text-text-muted">
            <span className="size-2.5 rotate-45 rounded-[2px] border border-text-muted bg-surface" />
            {d.milestoneLegend}
          </p>
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
