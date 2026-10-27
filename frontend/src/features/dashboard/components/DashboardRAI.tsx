import { Plus } from "lucide-react";
import { EmptyState } from "@/components/EmptyState";
import { RiskMatrix } from "@/components/RiskMatrix";
import { fr } from "@/i18n/fr";
import { cn } from "@/lib/utils";
import { MILESTONES, PHASES } from "../phases";
import { PageHeader, PreviewCard, PreviewSection, SkeletonTable } from "./preview";

const d = fr.dashboard;
const MILESTONE_ROWS: [string, string][] = [
  ["VI", d.milestoneVI],
  ["X", d.milestoneX],
  ["XIII", d.milestoneXIII],
  ["XVIII", d.milestoneXVIII],
];

export function DashboardRAI() {
  return (
    <>
      <PageHeader title={d.raiTitle} userRole="RAI" />
      <EmptyState
        title={d.emptyTitle}
        description={d.raiText}
        action={{ label: d.raiAction, icon: Plus, note: `${d.availableAtLot} ${d.raiLot}` }}
      />
      <PreviewSection>
        <PreviewCard
          title={d.missionsByPhase}
          meta={`${d.programme} 2026`}
          span={8}
          bodyClassName="p-5"
        >
          <div className="grid gap-x-6 gap-y-6 sm:grid-cols-[10fr_4fr_4fr]">
            {PHASES.map((phase) => (
              <div key={phase.name}>
                <p className="text-sm font-semibold">{phase.name}</p>
                <p className="text-xs text-text-muted">{phase.range}</p>
                <p className="mt-4 text-2xl font-semibold text-text-muted tabular-nums">
                  {fr.dashboard.placeholderValue}
                </p>
                <div className="mt-3 flex gap-[3px]">
                  {phase.steps.map((step) => (
                    <i
                      key={step}
                      className={cn(
                        "h-1.5 flex-1 rounded-[2px] not-italic",
                        MILESTONES.includes(step) ? "bg-text-muted/60" : "bg-border/75",
                      )}
                    />
                  ))}
                </div>
              </div>
            ))}
          </div>
        </PreviewCard>

        <PreviewCard title={d.milestones} meta={d.milestonesMeta} span={4}>
          <ul>
            {MILESTONE_ROWS.map(([code, label]) => (
              <li
                key={code}
                className="flex h-11 items-center gap-3 border-b border-border px-5 text-sm last:border-b-0"
              >
                <span className="inline-flex h-6 min-w-12 items-center justify-center rounded-sm border border-border bg-surface px-1.5 text-xs font-medium tabular-nums">
                  {code}
                </span>
                <span className="flex-1">{label}</span>
                <span className="text-text-muted">{d.placeholderValue}</span>
              </li>
            ))}
          </ul>
        </PreviewCard>

        <PreviewCard title={d.lateRecommendations} meta={d.overdue} span={8}>
          <SkeletonTable
            columns={[
              { label: d.colRecommendation, width: 150 },
              { label: d.colMission, width: 80 },
              { label: d.colEntity, width: 100 },
              { label: d.colDueDate, width: 72 },
              { label: d.colDelay, width: 28, numeric: true },
            ]}
          />
        </PreviewCard>

        <PreviewCard
          title={d.criticality}
          meta={d.matrix}
          span={4}
          decorative={false}
          bodyClassName="p-5"
        >
          <RiskMatrix />
        </PreviewCard>
      </PreviewSection>
    </>
  );
}
