import { useState } from "react";
import { isApiError } from "@/api/errors";
import { ALERT_CLASS } from "@/components/form/FormField";
import { ListIncompleteAlert } from "@/components/ListIncompleteAlert";
import { Button } from "@/components/ui/button";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { ConfirmActionDialog } from "@/features/missions/components/ConfirmActionDialog";
import { RiskLevelBadge } from "@/features/referentiel/components/RiskLevelBadge";
import type { NiveauRisque } from "@/features/referentiel/types";
import { fr } from "@/i18n/fr";
import { useAuditFramework, useDeleteMarcLine, useInitializeMarc, useMarcLines } from "../api";
import { EVALUATION_CONCEPTION_LABELS, NATURE_CONTROLE_LABELS } from "../labels";
import type { LigneMarc } from "../types";
import { Heading, type HeadingLevel } from "./Heading";
import { MarcLineDialog } from "./MarcLineDialog";

const t = fr.analyseVVI;

type Props = { missionId: string; editable: boolean; level?: HeadingLevel };

function dash(value: string | null | undefined): string {
  return value ? value : "—";
}

/** Nom accessible unique d'une ligne : risque, puis contrôle existant ou opération, sinon rang. */
function lineLabel(l: LigneMarc, index: number): string {
  const detail = l.controle_existant || l.operation || l.objectif_controle;
  return `${l.risque_code} — ${detail || `ligne ${index + 1}`}`;
}

function Appreciation({ value }: { value: LigneMarc["appreciation"] }) {
  if (value === "FORCE") {
    return <span className="font-medium text-success-text">✓ {t.forceLabel}</span>;
  }
  if (value === "FAIBLESSE") {
    return <span className="font-medium text-destructive">⚠ {t.weaknessLabel}</span>;
  }
  return <span>—</span>;
}

/** Matrice des risques et contrôles, groupée par risque. Les droits viennent du serveur (`editable`). */
export function MarcTable({ missionId, editable, level = 3 }: Props) {
  const lines = useMarcLines(missionId);
  const framework = useAuditFramework(missionId);
  const initialize = useInitializeMarc();
  const remove = useDeleteMarcLine();
  const [editing, setEditing] = useState<LigneMarc | null>(null);
  const [creating, setCreating] = useState(false);
  const [deleting, setDeleting] = useState<LigneMarc | null>(null);
  const [initError, setInitError] = useState<string | null>(null);

  if (lines.isError) {
    return (
      <div role="alert" className={ALERT_CLASS}>
        <p>{t.loadError}</p>
        <Button
          type="button"
          variant="outline"
          size="sm"
          className="mt-2"
          onClick={() => void lines.refetch()}
        >
          {fr.common.retry}
        </Button>
      </div>
    );
  }
  if (lines.isPending) {
    return (
      <p role="status" className="text-sm text-text-muted">
        {fr.common.loading}
      </p>
    );
  }

  const rows = lines.data.results;
  const groups = new Map<string, LigneMarc[]>();
  for (const l of rows) groups.set(l.risque, [...(groups.get(l.risque) ?? []), l]);
  const uncovered = framework.data?.risques_non_couverts ?? [];
  const columns = 9 + (editable ? 1 : 0);

  async function onInitialize() {
    setInitError(null);
    try {
      await initialize.mutateAsync({ missionId });
    } catch (e) {
      setInitError(isApiError(e) ? e.detail : fr.errors.generic);
    }
  }

  return (
    <section aria-labelledby="marc-title" className="marc-print grid gap-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <Heading level={level} id="marc-title" className="text-base font-semibold">
          {t.marcTitle}
        </Heading>
        {editable && (
          <div className="flex flex-wrap gap-2 print:hidden">
            <Button
              type="button"
              variant="outline"
              disabled={initialize.isPending}
              onClick={() => void onInitialize()}
            >
              {t.initialize}
            </Button>
            <Button type="button" onClick={() => setCreating(true)}>
              {t.addControl}
            </Button>
          </div>
        )}
      </div>
      {initError && (
        <p role="alert" className={ALERT_CLASS}>
          {initError}
        </p>
      )}
      {uncovered.length > 0 && (
        <p role="status" className="rounded-md border border-warning/50 p-3 text-sm">
          {t.uncovered.replace("{codes}", uncovered.join(", "))}
        </p>
      )}
      {framework.isError && (
        <p role="alert" className={ALERT_CLASS}>
          {t.frameworkError}
        </p>
      )}
      <ListIncompleteAlert count={lines.data.count} loaded={rows.length} />
      <div className="overflow-hidden rounded-md border border-border">
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
              {editable && (
                <TableHead className="print:hidden">
                  <span className="sr-only">{fr.common.actions}</span>
                </TableHead>
              )}
            </TableRow>
          </TableHeader>
          <TableBody>
            {rows.length === 0 && (
              <TableRow>
                <TableCell colSpan={columns} className="text-text-muted">
                  {t.marcEmpty}
                </TableCell>
              </TableRow>
            )}
            {[...groups.entries()].map(([riskId, list]) => {
              const first = list[0];
              if (!first) return null;
              return [
                <TableRow key={`risk-${riskId}`} className="bg-surface-subtle">
                  <TableCell colSpan={columns} className="whitespace-normal font-medium">
                    <span className="mr-2">{first.risque_code}</span>
                    <span className="mr-2">{first.risque_libelle}</span>
                    <RiskLevelBadge niveau={first.risque_niveau as NiveauRisque} />
                  </TableCell>
                </TableRow>,
                ...list.map((l, i) => (
                  <TableRow key={l.id}>
                    <TableCell className="whitespace-normal">
                      {dash(l.objet_auditable_libelle)}
                    </TableCell>
                    <TableCell className="whitespace-normal">{dash(l.operation)}</TableCell>
                    <TableCell className="whitespace-normal">{dash(l.objectif_controle)}</TableCell>
                    <TableCell className="whitespace-normal">{dash(l.controle_attendu)}</TableCell>
                    <TableCell className="whitespace-normal">{dash(l.controle_existant)}</TableCell>
                    <TableCell>{l.nature ? NATURE_CONTROLE_LABELS[l.nature] : "—"}</TableCell>
                    <TableCell className="whitespace-normal">
                      {l.evaluation ? EVALUATION_CONCEPTION_LABELS[l.evaluation] : "—"}
                    </TableCell>
                    <TableCell>
                      <Appreciation value={l.appreciation} />
                    </TableCell>
                    <TableCell>{l.cle ? t.keyYes : t.keyNo}</TableCell>
                    {editable && (
                      <TableCell className="print:hidden">
                        <div className="flex flex-wrap gap-2">
                          <Button
                            type="button"
                            variant="outline"
                            size="sm"
                            aria-label={`${t.editControl} : ${lineLabel(l, i)}`}
                            onClick={() => setEditing(l)}
                          >
                            {fr.common.edit}
                          </Button>
                          <Button
                            type="button"
                            variant="outline"
                            size="sm"
                            aria-label={`${t.deleteControl} : ${lineLabel(l, i)}`}
                            onClick={() => setDeleting(l)}
                          >
                            {fr.common.delete}
                          </Button>
                        </div>
                      </TableCell>
                    )}
                  </TableRow>
                )),
              ];
            })}
          </TableBody>
        </Table>
      </div>
      {editable && (creating || editing) && (
        <MarcLineDialog
          open
          onOpenChange={(open) => {
            if (!open) {
              setCreating(false);
              setEditing(null);
            }
          }}
          missionId={missionId}
          line={editing ?? undefined}
        />
      )}
      {editable && (
        <ConfirmActionDialog
          open={deleting !== null}
          onOpenChange={(open) => !open && setDeleting(null)}
          title={t.deleteControlTitle}
          text={t.deleteControlText}
          confirmLabel={fr.common.delete}
          requireCheck={false}
          onConfirm={() =>
            deleting ? remove.mutateAsync({ id: deleting.id, missionId }) : Promise.resolve()
          }
        />
      )}
    </section>
  );
}
