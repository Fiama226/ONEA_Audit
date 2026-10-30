import { ALERT_CLASS } from "@/components/form/FormField";
import type { ZoneProps } from "@/features/missions/zones";
import { fr } from "@/i18n/fr";
import { usePlannedTests, useTestSheets } from "../api";
import { ValidationQueue } from "../components/ValidationQueue";

const t = fr.fiches;

/** Étape XIII : file de validation des fiches et suivi de l'avancement (D6). */
export function StepXIIIZone({ mission, step }: ZoneProps) {
  const id = `zone-XIII-${step.id}`;
  const tests = usePlannedTests({ mission: mission.id });
  const sheets = useTestSheets({ mission: mission.id });

  let body;
  if (tests.isPending || sheets.isPending) {
    body = <p role="status">{t.loading}</p>;
  } else if (tests.isError || sheets.isError) {
    body = (
      <p role="alert" className={ALERT_CLASS}>
        {t.loadError}
      </p>
    );
  } else {
    const active = tests.data.results.filter((test) => test.statut !== "ABANDONNE");
    const validated = active.filter((test) => test.fiche?.statut === "VALIDE").length;
    const complementary = active.filter((test) => test.complementaire);
    const abandoned = tests.data.results.filter((test) => test.statut === "ABANDONNE");
    body = (
      <>
        <p className="text-sm font-medium" role="status">
          {t.progress(validated, active.length)}
        </p>
        <section aria-labelledby={`${id}-queue`} className="grid gap-2">
          <h4 id={`${id}-queue`} className="text-sm font-semibold">
            {t.queueTitle}
          </h4>
          <ValidationQueue missionId={mission.id} sheets={sheets.data.results} />
        </section>
        {complementary.length > 0 && (
          <section aria-labelledby={`${id}-comp`} className="grid gap-1">
            <h4 id={`${id}-comp`} className="text-sm font-semibold">
              {t.complementaryTitle}
            </h4>
            <ul className="list-disc pl-5 text-sm">
              {complementary.map((test) => (
                <li key={test.id}>
                  {test.code} · {test.libelle}
                </li>
              ))}
            </ul>
          </section>
        )}
        {abandoned.length > 0 && (
          <section aria-labelledby={`${id}-aband`} className="grid gap-1">
            <h4 id={`${id}-aband`} className="text-sm font-semibold">
              {t.abandonedTitle}
            </h4>
            <ul className="list-disc pl-5 text-sm">
              {abandoned.map((test) => (
                <li key={test.id}>
                  {test.code} · {test.libelle} — {t.abandonedReason} : {test.motif_abandon}
                </li>
              ))}
            </ul>
          </section>
        )}
      </>
    );
  }

  return (
    <section aria-labelledby={id} className="grid gap-4">
      <h3 id={id} className="text-base font-semibold">
        {t.xiiiTitle}
      </h3>
      <p className="text-sm text-text-muted">{t.xiiiHelp}</p>
      {body}
    </section>
  );
}
