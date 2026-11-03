import { ALERT_CLASS } from "@/components/form/FormField";
import { fr } from "@/i18n/fr";
import { formatDateTime } from "@/lib/dates";
import { useFindingResponses } from "../api";
import { PositionBadge } from "./PositionBadge";
import { ScrollRegion } from "@/components/ui/scroll-region";

const t = fr.constatsUi;

/** Historique des réponses de l'audité : une ligne par réponse, version antérieure signalée. */
export function ReponsesHistory({ constatId }: { constatId: string }) {
  const responses = useFindingResponses(constatId);
  const id = `reponses-${constatId}`;

  let body;
  if (responses.isPending) {
    body = <p role="status">{fr.common.loading}</p>;
  } else if (responses.isError) {
    body = (
      <p role="alert" className={ALERT_CLASS}>
        {t.historyLoadError}
      </p>
    );
  } else if (responses.data.results.length === 0) {
    body = <p className="text-sm text-text-muted">{t.historyEmpty}</p>;
  } else {
    body = (
      <ScrollRegion label={t.historyCaption}>
        <table className="w-full text-left text-sm">
          <caption className="sr-only">{t.historyCaption}</caption>
          <thead>
            <tr className="border-b border-border text-text-muted">
              <th scope="col" className="py-2 pr-3">
                {t.historyCycle}
              </th>
              <th scope="col" className="py-2 pr-3">
                {t.historyPosition}
              </th>
              <th scope="col" className="py-2 pr-3">
                {t.historyComment}
              </th>
              <th scope="col" className="py-2 pr-3">
                {t.historyAuthor}
              </th>
              <th scope="col" className="py-2 pr-3">
                {t.historyDate}
              </th>
              <th scope="col" className="py-2">
                {t.historyFingerprint}
              </th>
            </tr>
          </thead>
          <tbody>
            {responses.data.results.map((r) => (
              <tr key={r.id} className="border-b border-border align-top">
                <td className="py-2 pr-3 tabular-nums">{r.cycle}</td>
                <td className="py-2 pr-3">
                  <div className="grid justify-items-start gap-1">
                    <PositionBadge position={r.position} />
                    {r.version_anterieure && (
                      <span className="text-xs text-text-muted">{t.historyStale}</span>
                    )}
                  </div>
                </td>
                <td className="py-2 pr-3 whitespace-pre-line">{r.commentaire || t.noValue}</td>
                <td className="py-2 pr-3">{r.auteur.nom_complet}</td>
                <td className="py-2 pr-3 whitespace-nowrap">
                  {formatDateTime(r.confirmation.confirme_le)}
                </td>
                <td className="py-2 font-mono text-xs break-all">{r.confirmation.empreinte}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </ScrollRegion>
    );
  }

  return (
    <section aria-labelledby={id} className="grid gap-2">
      <h3 id={id} className="text-base font-semibold">
        {t.historyTitle}
      </h3>
      {body}
    </section>
  );
}
