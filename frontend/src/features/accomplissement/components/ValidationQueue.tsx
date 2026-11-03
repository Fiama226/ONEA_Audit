import { Link } from "react-router-dom";
import { fr } from "@/i18n/fr";
import { useEvidence } from "../api";
import type { Fiche } from "../types";
import { ConclusionBadge } from "./ConclusionBadge";
import { ScrollRegion } from "@/components/ui/scroll-region";

const t = fr.fiches;

/** Nombre de pièces d'une fiche ; une erreur de chargement n'est jamais présentée comme zéro. */
function PieceCount({ ficheId }: { ficheId: string }) {
  const evidence = useEvidence(ficheId);
  if (evidence.isPending) return <span aria-busy="true">…</span>;
  if (evidence.isError) return <span title={t.piecesUnknown}>—</span>;
  return <span>{evidence.data.results.length}</span>;
}

type Props = { missionId: string; sheets: Fiche[] };

/** Fiches soumises en attente de validation (étape XIII). */
export function ValidationQueue({ missionId, sheets }: Props) {
  const queue = sheets.filter((sheet) => sheet.statut === "SOUMIS");
  if (queue.length === 0) return <p className="text-sm text-text-muted">{t.queueEmpty}</p>;
  return (
    <ScrollRegion label={t.queueTable}>
      <table className="w-full text-left text-sm" aria-label={t.queueTable}>
        <thead>
          <tr className="border-b border-border text-xs text-text-muted">
            <th scope="col" className="py-2 pr-3">
              {t.code}
            </th>
            <th scope="col" className="py-2 pr-3">
              {t.label}
            </th>
            <th scope="col" className="py-2 pr-3">
              {t.author}
            </th>
            <th scope="col" className="py-2 pr-3">
              {t.conclusion}
            </th>
            <th scope="col" className="py-2 pr-3">
              {t.pieces}
            </th>
            <th scope="col" className="py-2">
              {t.actions}
            </th>
          </tr>
        </thead>
        <tbody>
          {queue.map((sheet) => (
            <tr key={sheet.id} className="border-b border-border align-top">
              <td className="py-2 pr-3">{sheet.test_code}</td>
              <td className="py-2 pr-3">{sheet.test_libelle}</td>
              <td className="py-2 pr-3">{sheet.auteur_detail.nom_complet}</td>
              <td className="py-2 pr-3">
                <ConclusionBadge conclusion={sheet.conclusion} />
              </td>
              <td className="py-2 pr-3">
                <PieceCount ficheId={sheet.id} />
              </td>
              <td className="py-2">
                <Link
                  className="text-primary underline"
                  to={`/missions/${missionId}/fiches/${sheet.id}`}
                  aria-label={`${t.open} ${sheet.test_code}`}
                >
                  {t.open}
                </Link>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </ScrollRegion>
  );
}
