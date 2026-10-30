import { ALERT_CLASS } from "@/components/form/FormField";
import { Button } from "@/components/ui/button";
import { useFindings } from "@/features/constats/api";
import { PositionBadge } from "@/features/constats/components/PositionBadge";
import { fr } from "@/i18n/fr";

const t = fr.rapportProvisoire;

/** Constats validés à présenter en réunion de clôture, avec la position de l'audité. */
export function ClosingFindingsPanel({ missionId }: { missionId: string }) {
  const findings = useFindings({ mission: missionId });

  let body;
  if (findings.isError) {
    body = (
      <div role="alert" className={`${ALERT_CLASS} flex flex-wrap items-center gap-3`}>
        <span>{t.loadError}</span>
        <Button type="button" variant="outline" size="sm" onClick={() => void findings.refetch()}>
          {fr.common.retry}
        </Button>
      </div>
    );
  } else if (findings.isPending) {
    body = (
      <p role="status" className="text-sm text-text-muted">
        {fr.common.loading}
      </p>
    );
  } else {
    const validated = findings.data.results.filter((c) => c.statut === "VALIDE");
    body =
      validated.length === 0 ? (
        <p className="text-sm text-text-muted">{t.findingsEmpty}</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <caption className="sr-only">{t.findingsLabel}</caption>
            <thead>
              <tr className="border-b border-border">
                <th scope="col" className="py-2 pr-3 font-medium">
                  {t.colReference}
                </th>
                <th scope="col" className="py-2 pr-3 font-medium">
                  {t.colTitle}
                </th>
                <th scope="col" className="py-2 pr-3 font-medium">
                  {t.colLevel}
                </th>
                <th scope="col" className="py-2 font-medium">
                  {t.colPosition}
                </th>
              </tr>
            </thead>
            <tbody>
              {validated.map((c) => (
                <tr key={c.id} className="border-b border-border/60">
                  <td className="py-2 pr-3">{c.reference}</td>
                  <td className="py-2 pr-3">{c.titre}</td>
                  <td className="py-2 pr-3">{c.niveau ?? t.levelNone}</td>
                  <td className="py-2">
                    {c.derniere_reponse ? (
                      <PositionBadge position={c.derniere_reponse.position} />
                    ) : (
                      <span className="text-text-muted">{t.positionNone}</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      );
  }

  return (
    <section aria-labelledby="closing-findings" className="grid gap-2">
      <h3 id="closing-findings" className="text-base font-semibold">
        {t.findingsTitle}
      </h3>
      <p className="text-sm text-text-muted">{t.findingsHelp}</p>
      {body}
    </section>
  );
}
