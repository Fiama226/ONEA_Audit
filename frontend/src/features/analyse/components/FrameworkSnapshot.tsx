import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { RiskLevelBadge } from "@/features/referentiel/components/RiskLevelBadge";
import { NIVEAU_LABELS } from "@/features/referentiel/labels";
import type { NiveauRisque } from "@/features/referentiel/types";
import { fr } from "@/i18n/fr";
import { formatDate } from "@/lib/dates";
import {
  EVALUATION_CONCEPTION_LABELS,
  NATURE_CONTROLE_LABELS,
  TYPE_FORCE_FAIBLESSE_LABELS,
} from "../labels";
import type { InstantaneReferentiel } from "../types";

const t = fr.analyseVVI;

type Row = Record<string, unknown>;

function rowsOf(data: Row, key: string): Row[] {
  const value = data[key];
  return Array.isArray(value)
    ? (value.filter((v) => typeof v === "object" && v !== null) as Row[])
    : [];
}

function text(row: Row, key: string): string {
  const v = row[key];
  return typeof v === "string" && v !== "" ? v : "—";
}

/** Libellé français d'un code de l'instantané ; un code inconnu reste affiché tel quel. */
function label(map: Record<string, string>, row: Row, key: string): string {
  const code = text(row, key);
  return map[code] ?? code;
}

function Appreciation({ code }: { code: string }) {
  if (code === "FORCE")
    return <span className="font-medium text-success-text">✓ {t.forceLabel}</span>;
  if (code === "FAIBLESSE") {
    return <span className="font-medium text-destructive">⚠ {t.weaknessLabel}</span>;
  }
  return <span>—</span>;
}

/** Instantané validé : contenu figé au moment de la confirmation, mêmes colonnes que la MARC. */
export function FrameworkSnapshot({ snapshot }: { snapshot: InstantaneReferentiel }) {
  const lines = rowsOf(snapshot.donnees, "lignes_marc");
  const risks = new Map(rowsOf(snapshot.donnees, "risques").map((r) => [text(r, "id"), r]));
  const sw = rowsOf(snapshot.donnees, "forces_faiblesses");
  const groups = new Map<string, Row[]>();
  for (const l of lines) {
    const key = text(l, "risque_id");
    groups.set(key, [...(groups.get(key) ?? []), l]);
  }

  return (
    <div className="grid gap-4">
      <p className="text-sm font-medium">
        {t.snapshotNotice.replace("{date}", formatDate(snapshot.confirmation.confirme_le))}
      </p>
      <div className="marc-print overflow-hidden rounded-md border border-border">
        <Table aria-label={t.marcCaption} className="text-xs">
          <TableHeader>
            <TableRow>
              <TableHead>{t.colAuditable}</TableHead>
              <TableHead>{t.colOperation}</TableHead>
              <TableHead>{t.colObjective}</TableHead>
              <TableHead>{t.colExpected}</TableHead>
              <TableHead>{t.colExisting}</TableHead>
              <TableHead>{t.colNature}</TableHead>
              <TableHead>{t.colEvaluation}</TableHead>
              <TableHead>{t.colAppreciation}</TableHead>
              <TableHead>{t.colKey}</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {lines.length === 0 && (
              <TableRow>
                <TableCell colSpan={9} className="text-text-muted">
                  {t.snapshotEmpty}
                </TableCell>
              </TableRow>
            )}
            {[...groups.entries()].map(([riskId, list]) => {
              const risk = risks.get(riskId);
              const niveau = risk ? text(risk, "niveau") : "";
              return [
                <TableRow key={`risk-${riskId}`} className="bg-surface-subtle">
                  <TableCell colSpan={9} className="whitespace-normal font-medium">
                    {risk ? (
                      <>
                        <span className="mr-2">{text(risk, "code")}</span>
                        <span className="mr-2">{text(risk, "libelle")}</span>
                        {niveau in NIVEAU_LABELS ? (
                          <RiskLevelBadge niveau={niveau as NiveauRisque} />
                        ) : (
                          niveau
                        )}
                      </>
                    ) : (
                      "—"
                    )}
                  </TableCell>
                </TableRow>,
                ...list.map((l, i) => (
                  <TableRow key={`${text(l, "id")}-${i}`}>
                    <TableCell className="whitespace-normal">
                      {text(l, "objet_auditable")}
                    </TableCell>
                    <TableCell className="whitespace-normal">{text(l, "operation")}</TableCell>
                    <TableCell className="whitespace-normal">
                      {text(l, "objectif_controle")}
                    </TableCell>
                    <TableCell className="whitespace-normal">
                      {text(l, "controle_attendu")}
                    </TableCell>
                    <TableCell className="whitespace-normal">
                      {text(l, "controle_existant")}
                    </TableCell>
                    <TableCell>{label(NATURE_CONTROLE_LABELS, l, "nature")}</TableCell>
                    <TableCell className="whitespace-normal">
                      {label(EVALUATION_CONCEPTION_LABELS, l, "evaluation")}
                    </TableCell>
                    <TableCell>
                      <Appreciation
                        code={typeof l["appreciation"] === "string" ? l["appreciation"] : ""}
                      />
                    </TableCell>
                    <TableCell>{l["cle"] === true ? t.keyYes : t.keyNo}</TableCell>
                  </TableRow>
                )),
              ];
            })}
          </TableBody>
        </Table>
      </div>
      <div className="overflow-hidden rounded-md border border-border">
        <Table aria-label={t.swTitle} className="text-xs">
          <TableHeader>
            <TableRow>
              <TableHead>{t.typeLabel}</TableHead>
              <TableHead>{t.colWording}</TableHead>
              <TableHead>{t.colConsequence}</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {sw.length === 0 && (
              <TableRow>
                <TableCell colSpan={3} className="text-text-muted">
                  {t.swEmpty}
                </TableCell>
              </TableRow>
            )}
            {sw.map((r, i) => (
              <TableRow key={i}>
                <TableCell>{label(TYPE_FORCE_FAIBLESSE_LABELS, r, "type")}</TableCell>
                <TableCell className="whitespace-normal">{text(r, "libelle")}</TableCell>
                <TableCell className="whitespace-normal">{text(r, "consequence")}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
    </div>
  );
}
