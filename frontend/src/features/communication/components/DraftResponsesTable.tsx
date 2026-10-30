import { StatusPill } from "@/components/StatusPill";
import { fr } from "@/i18n/fr";
import { formatDateTime } from "@/lib/dates";
import type { ReponseRapport, RapportProvisoire } from "../types";

const t = fr.rapportProvisoire;

type Props = { provisoire: RapportProvisoire; responses: readonly ReponseRapport[] };

/** Suivi des réponses : par constat, entité attendue, date de réception et mention « Hors délai ». */
export function DraftResponsesTable({ provisoire, responses }: Props) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-left text-sm">
        <caption className="sr-only">{t.responsesLabel}</caption>
        <thead>
          <tr className="border-b border-border">
            <th scope="col" className="py-2 pr-3 font-medium">
              {t.colFinding}
            </th>
            <th scope="col" className="py-2 pr-3 font-medium">
              {t.colExpectedFrom}
            </th>
            <th scope="col" className="py-2 font-medium">
              {t.colReceivedOn}
            </th>
          </tr>
        </thead>
        <tbody>
          {provisoire.constats.map((constat) => {
            const reponse = responses.find((r) => r.constat === constat.id);
            return (
              <tr key={constat.id} className="border-b border-border/60">
                <td className="py-2 pr-3">
                  {constat.reference} · {constat.titre}
                </td>
                <td className="py-2 pr-3">{constat.entite}</td>
                <td className="py-2">
                  {reponse ? (
                    <span className="flex flex-wrap items-center gap-2">
                      {formatDateTime(reponse.confirmation.confirme_le)}
                      {reponse.hors_delai && <StatusPill label={t.late} tone="warning" />}
                    </span>
                  ) : (
                    <span className="text-text-muted">{t.pending}</span>
                  )}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
