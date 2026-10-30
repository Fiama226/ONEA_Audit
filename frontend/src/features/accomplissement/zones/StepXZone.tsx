import { ALERT_CLASS } from "@/components/form/FormField";
import { Button } from "@/components/ui/button";
import type { ZoneProps } from "@/features/missions/zones";
import { formatDate } from "@/lib/dates";
import { fr } from "@/i18n/fr";
import { useSnapshots } from "../api";
import { ProgramSummary } from "../components/ProgramSummary";

const t = fr.programme;

/** « 3f2a1b…9c1b » : début et fin de l'empreinte SHA-256, complète dans l'info-bulle. */
function shortHash(hash: string): string {
  return hash.length > 12 ? `${hash.slice(0, 4)}…${hash.slice(-4)}` : hash;
}

/** Étape X : synthèse du programme en lecture, versions validées ; la validation reste au jalon. */
export function StepXZone({ mission, step }: ZoneProps) {
  const snapshots = useSnapshots(mission.id);
  const id = `zone-X-${step.id}`;

  let list;
  if (snapshots.isPending) {
    list = (
      <p role="status" className="text-sm text-text-muted">
        {fr.common.loading}
      </p>
    );
  } else if (snapshots.isError) {
    list = (
      <p role="alert" className={ALERT_CLASS}>
        {t.loadError}
      </p>
    );
  } else if (snapshots.data.results.length === 0) {
    list = <p className="text-sm text-text-muted">{t.snapshotsNone}</p>;
  } else {
    list = (
      <ul aria-label={t.snapshotsLabel} className="grid gap-1 text-sm">
        {snapshots.data.results.map((s) => (
          <li key={s.id}>
            {t.snapshotLine
              .replace("{date}", formatDate(s.valide_le))
              .replace("{name}", s.valide_par.nom_complet)
              .replace("{hash}", "")}
            <abbr title={s.empreinte} className="no-underline">
              {shortHash(s.empreinte)}
            </abbr>
          </li>
        ))}
      </ul>
    );
  }

  return (
    <section aria-labelledby={id} className="grid gap-4">
      <style media="print">{"@page { size: A4; }"}</style>
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h3 id={id} className="text-base font-semibold">
          {t.printTitle}
        </h3>
        <Button
          type="button"
          variant="outline"
          className="print:hidden"
          onClick={() => window.print()}
        >
          {t.print}
        </Button>
      </div>
      <p className="hidden text-sm print:block">
        {t.printMission.replace("{reference}", mission.reference).replace("{titre}", mission.titre)}
      </p>
      <ProgramSummary missionId={mission.id} />
      <div className="grid gap-2">
        <h4 className="font-semibold">{t.snapshotsTitle}</h4>
        {list}
      </div>
      <p className="text-sm print:hidden">{t.validateReminder}</p>
    </section>
  );
}
