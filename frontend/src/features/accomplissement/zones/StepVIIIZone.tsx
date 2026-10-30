import { useState } from "react";
import { ALERT_CLASS } from "@/components/form/FormField";
import { useAuditObjectives } from "@/features/analyse/api";
import type { ZoneProps } from "@/features/missions/zones";
import { fr } from "@/i18n/fr";
import { usePlannedTests, useWorkPrograms } from "../api";
import { PlannedTestDialog } from "../components/PlannedTestDialog";
import { ProgrammeCard, type ObjectiveRef } from "../components/ProgrammeCard";

const t = fr.programme;
const OPEN = ["EN_COURS", "RENVOYEE"];

/** Étape VIII : programme de travail par objectif retenu (droits du serveur). */
export function StepVIIIZone({ mission, step }: ZoneProps) {
  const objectives = useAuditObjectives(mission.id);
  const programs = useWorkPrograms(mission.id);
  const tests = usePlannedTests({ mission: mission.id });
  const [target, setTarget] = useState<{ programmeId: string; code: string } | null>(null);
  const id = `zone-VIII-${step.id}`;
  const open = OPEN.includes(step.statut);

  let body;
  if (objectives.isPending || programs.isPending || tests.isPending) {
    body = (
      <p role="status" className="text-sm text-text-muted">
        {fr.common.loading}
      </p>
    );
  } else if (objectives.isError || programs.isError || tests.isError) {
    body = (
      <p role="alert" className={ALERT_CLASS}>
        {t.loadError}
      </p>
    );
  } else {
    const cards = new Map<string, ObjectiveRef>();
    for (const o of objectives.data.results.filter((x) => x.retenu)) {
      cards.set(o.id, { id: o.id, code: o.code, libelle: o.libelle ?? "" });
    }
    // Un programme déjà établi reste visible même si son objectif n'est plus retenu.
    for (const p of programs.data.results) {
      if (!cards.has(p.objectif)) cards.set(p.objectif, p.objectif_detail);
    }
    const list = [...cards.values()];
    body =
      list.length === 0 ? (
        <p role="status" className="rounded-md border border-border p-3 text-sm">
          {t.noObjectives}
        </p>
      ) : (
        <div className="grid gap-4">
          {list.map((objective) => {
            const programme = programs.data.results.find((p) => p.objectif === objective.id);
            return (
              <ProgrammeCard
                key={objective.id}
                missionId={mission.id}
                objective={objective}
                programme={programme}
                tests={tests.data.results.filter((x) => x.programme === programme?.id)}
                canCreate={open && mission.mes_droits.contribuer}
                onAddTest={(p, o) => setTarget({ programmeId: p.id, code: o.code })}
              />
            );
          })}
        </div>
      );
  }

  return (
    <section aria-labelledby={id} className="grid gap-4">
      <h3 id={id} className="text-base font-semibold">
        {t.title}
      </h3>
      {!open && <p className="text-sm text-text-muted">{t.readOnly}</p>}
      {body}
      <PlannedTestDialog
        missionId={mission.id}
        target={target}
        onOpenChange={(next) => {
          if (!next) setTarget(null);
        }}
      />
    </section>
  );
}
