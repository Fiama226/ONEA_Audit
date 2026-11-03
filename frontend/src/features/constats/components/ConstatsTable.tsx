import { Link } from "react-router-dom";
import { StatusPill } from "@/components/StatusPill";
import { RiskLevelBadge } from "@/features/referentiel/components/RiskLevelBadge";
import { fr } from "@/i18n/fr";
import type { Constat } from "../types";
import { ConstatStatusBadge } from "./ConstatStatusBadge";
import { ScrollRegion } from "@/components/ui/scroll-region";

const t = fr.constatsUi;

/** Réponse du cycle courant ; une réponse d'un cycle antérieur compte comme « En attente ». */
export function ReponseCell({ constat }: { constat: Constat }) {
  const reponse = constat.derniere_reponse;
  if (!reponse || !constat.reponse_cycle_courant) {
    return <StatusPill label={t.responseWaiting} tone="neutral" />;
  }
  return reponse.position === "ACCORD" ? (
    <StatusPill label={t.responseAgreement} tone="success" />
  ) : (
    <StatusPill label={t.responseDisagreement} tone="danger" />
  );
}

/** Tableau des constats d'une mission ; les liens mènent à la page du constat. */
export function ConstatsTable({ missionId, constats }: { missionId: string; constats: Constat[] }) {
  return (
    <ScrollRegion label={t.tableCaption}>
      <table className="w-full text-left text-sm">
        <caption className="sr-only">{t.tableCaption}</caption>
        <thead>
          <tr className="border-b border-border text-text-muted">
            <th scope="col" className="py-2 pr-3">
              {t.colReference}
            </th>
            <th scope="col" className="py-2 pr-3">
              {t.colTitle}
            </th>
            <th scope="col" className="py-2 pr-3">
              {t.colEntity}
            </th>
            <th scope="col" className="py-2 pr-3">
              {t.colLevel}
            </th>
            <th scope="col" className="py-2 pr-3">
              {t.colStatus}
            </th>
            <th scope="col" className="py-2">
              {t.colResponse}
            </th>
          </tr>
        </thead>
        <tbody>
          {constats.map((c) => (
            <tr key={c.id} className="border-b border-border">
              <td className="py-2 pr-3 font-medium">
                <Link
                  className="text-primary underline"
                  to={`/missions/${missionId}/constats/${c.id}`}
                >
                  {c.reference}
                </Link>
              </td>
              <td className="py-2 pr-3">{c.titre || t.noValue}</td>
              <td className="py-2 pr-3">{c.entite_detail.libelle}</td>
              <td className="py-2 pr-3">
                {c.niveau ? <RiskLevelBadge niveau={c.niveau} /> : t.noValue}
              </td>
              <td className="py-2 pr-3">
                <ConstatStatusBadge statut={c.statut} />
              </td>
              <td className="py-2">
                <ReponseCell constat={c} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </ScrollRegion>
  );
}
