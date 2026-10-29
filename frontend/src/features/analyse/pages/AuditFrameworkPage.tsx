import { useState } from "react";
import { useParams } from "react-router-dom";
import { ALERT_CLASS } from "@/components/form/FormField";
import { EmptyState } from "@/components/EmptyState";
import { Button } from "@/components/ui/button";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { fr } from "@/i18n/fr";
import { formatDate } from "@/lib/dates";
import { useAuditFramework, useFrameworkSnapshot } from "../api";
import { FrameworkStatusPanel } from "../components/FrameworkStatusPanel";
import { MarcTable } from "../components/MarcTable";
import { OpinionDialog } from "../components/OpinionDialog";
import { StrengthsWeaknessesTable } from "../components/StrengthsWeaknessesTable";
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

/** Instantané validé : contenu figé au moment de la confirmation. */
function SnapshotView({ snapshot }: { snapshot: InstantaneReferentiel }) {
  const lines = rowsOf(snapshot.donnees, "lignes_marc");
  const risks = new Map(rowsOf(snapshot.donnees, "risques").map((r) => [text(r, "id"), r]));
  const sw = rowsOf(snapshot.donnees, "forces_faiblesses");
  return (
    <div className="grid gap-4">
      <p className="text-sm font-medium">
        {t.snapshotNotice.replace("{date}", formatDate(snapshot.confirmation.confirme_le))}
      </p>
      <div className="overflow-x-auto rounded-md border border-border">
        <Table aria-label={t.marcCaption} className="text-xs">
          <TableHeader>
            <TableRow>
              <TableHead>{t.risk}</TableHead>
              <TableHead>{t.colAuditable}</TableHead>
              <TableHead>{t.colOperation}</TableHead>
              <TableHead>{t.colExisting}</TableHead>
              <TableHead>{t.colEvaluation}</TableHead>
              <TableHead>{t.colAppreciation}</TableHead>
              <TableHead>{t.colKey}</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {lines.map((l, i) => {
              const risk = risks.get(text(l, "risque_id"));
              return (
                <TableRow key={text(l, "id") + i}>
                  <TableCell className="whitespace-normal">
                    {risk ? `${text(risk, "code")} ${text(risk, "libelle")}` : "—"}
                  </TableCell>
                  <TableCell className="whitespace-normal">{text(l, "objet_auditable")}</TableCell>
                  <TableCell className="whitespace-normal">{text(l, "operation")}</TableCell>
                  <TableCell className="whitespace-normal">
                    {text(l, "controle_existant")}
                  </TableCell>
                  <TableCell>{text(l, "evaluation")}</TableCell>
                  <TableCell>{text(l, "appreciation")}</TableCell>
                  <TableCell>{l["cle"] === true ? t.keyYes : t.keyNo}</TableCell>
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
      </div>
      <div className="overflow-x-auto rounded-md border border-border">
        <Table aria-label={t.swTitle} className="text-xs">
          <TableHeader>
            <TableRow>
              <TableHead>{t.typeLabel}</TableHead>
              <TableHead>{t.colWording}</TableHead>
              <TableHead>{t.colConsequence}</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {sw.map((r, i) => (
              <TableRow key={i}>
                <TableCell>{r["type"] === "FORCE" ? t.forceLabel : t.weaknessLabel}</TableCell>
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

/** Référentiel d'audit de la mission (onglet) : synthèse, MARC, forces et faiblesses, avis des audités. */
export function AuditFrameworkPage() {
  const { id } = useParams();
  const framework = useAuditFramework(id);
  const validated = framework.data?.statut === "VALIDE";
  const snapshot = useFrameworkSnapshot(id, validated);
  const [opinionOpen, setOpinionOpen] = useState(false);

  if (framework.isError) {
    return (
      <p role="alert" className={ALERT_CLASS}>
        {t.loadError}
      </p>
    );
  }
  if (framework.isPending || id === undefined) {
    return (
      <p role="status" className="text-sm text-text-muted">
        {fr.common.loading}
      </p>
    );
  }
  const data = framework.data;
  if (!data.mes_droits.voir_referentiel) {
    return (
      <EmptyState title={t.notBroadcast} description={t.notBroadcastText} illustration={false} />
    );
  }

  return (
    <section aria-labelledby="framework-title" className="grid gap-6">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 id="framework-title" className="text-lg font-semibold">
          {t.printTitle}
        </h2>
        <div className="flex flex-wrap gap-2 print:hidden">
          {data.mes_droits.donner_avis && (
            <Button type="button" onClick={() => setOpinionOpen(true)}>
              {t.giveOpinion}
            </Button>
          )}
          <Button type="button" variant="outline" onClick={() => window.print()}>
            {t.printFramework}
          </Button>
        </div>
      </div>
      <FrameworkStatusPanel framework={data} />
      {validated ? (
        <section aria-labelledby="snapshot-title" className="grid gap-3">
          <h3 id="snapshot-title" className="text-base font-semibold">
            {t.snapshotTitle}
          </h3>
          {snapshot.isError && (
            <p role="alert" className={ALERT_CLASS}>
              {t.snapshotError}
            </p>
          )}
          {snapshot.isPending && (
            <p role="status" className="text-sm text-text-muted">
              {t.snapshotLoading}
            </p>
          )}
          {snapshot.data && <SnapshotView snapshot={snapshot.data} />}
        </section>
      ) : (
        <>
          <MarcTable missionId={id} editable={false} />
          <StrengthsWeaknessesTable missionId={id} editable={false} />
        </>
      )}
      {data.mes_droits.donner_avis && opinionOpen && (
        <OpinionDialog open onOpenChange={setOpinionOpen} missionId={id} />
      )}
    </section>
  );
}
