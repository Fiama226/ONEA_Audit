import { Link } from "react-router-dom";
import { ALERT_CLASS } from "@/components/form/FormField";
import { Button } from "@/components/ui/button";
import { useTestSheets } from "@/features/accomplissement/api";
import type { ZoneProps } from "@/features/missions/zones";
import { fr } from "@/i18n/fr";
import { useFindings } from "../api";
import { ConstatsTable } from "../components/ConstatsTable";

const t = fr.constatsUi;

/** Étape XIV : constats de la mission et fiches ANOMALIE qui n'en ont pas encore (droits du serveur). */
export function StepXIVZone({ mission, step }: ZoneProps) {
  const findings = useFindings({ mission: mission.id });
  const sheets = useTestSheets({ mission: mission.id });
  const id = `constats-xiv-${step.id}`;
  const base = `/missions/${mission.id}/constats`;

  let table;
  if (findings.isPending) {
    table = <p role="status">{fr.common.loading}</p>;
  } else if (findings.isError) {
    table = (
      <p role="alert" className={ALERT_CLASS}>
        {t.loadError}
      </p>
    );
  } else if (findings.data.results.length === 0) {
    table = <p className="text-sm text-text-muted">{t.empty}</p>;
  } else {
    table = <ConstatsTable missionId={mission.id} constats={findings.data.results} />;
  }

  const orphans = sheets.data?.results.filter(
    (f) => f.statut === "VALIDE" && f.conclusion === "ANOMALIE" && f.constats.length === 0,
  );

  return (
    <section aria-labelledby={id} className="grid gap-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h3 id={id} className="text-base font-semibold">
          {t.zoneTitle}
        </h3>
        {mission.mes_droits.contribuer && (
          <Button asChild>
            <Link to={`${base}/nouveau`}>{t.create}</Link>
          </Button>
        )}
      </div>
      {table}
      {sheets.isError && (
        <p role="alert" className={ALERT_CLASS}>
          {t.unlinkedLoadError}
        </p>
      )}
      {orphans && orphans.length > 0 && (
        <section
          aria-labelledby={`${id}-orphans`}
          className="grid gap-2 rounded-md border border-border p-3"
        >
          <h4 id={`${id}-orphans`} className="text-sm font-semibold">
            {t.unlinkedTitle}
          </h4>
          <p className="text-sm text-text-muted">{t.unlinkedHelp}</p>
          <ul className="grid gap-2">
            {orphans.map((f) => (
              <li key={f.id} className="flex flex-wrap items-center justify-between gap-2 text-sm">
                <span>
                  {f.test_code} · {f.test_libelle}
                </span>
                {mission.mes_droits.contribuer && (
                  <Button asChild variant="outline" size="sm">
                    <Link
                      to={`${base}/nouveau?fiche=${f.id}`}
                      aria-label={`${t.createFromFiche} ${f.test_code}`}
                    >
                      {t.createFromFiche}
                    </Link>
                  </Button>
                )}
              </li>
            ))}
          </ul>
        </section>
      )}
    </section>
  );
}
