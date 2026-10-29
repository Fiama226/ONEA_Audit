import { CheckCircle2, MinusCircle } from "lucide-react";
import { useId, useState } from "react";
import { isApiError } from "@/api/errors";
import { EmptyState } from "@/components/EmptyState";
import { ALERT_CLASS } from "@/components/form/FormField";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { fr } from "@/i18n/fr";
import { useAuditObjectives, useInitializeObjectives, useSaveAuditObjective } from "../api";
import { MOTIF_NON_TEST_LABELS } from "../labels";
import type { ObjectifAudit } from "../types";
import { NonTestDialog } from "./NonTestDialog";

const t = fr.analyseVII;

function errorText(e: unknown, field?: string): string {
  if (!isApiError(e)) return fr.errors.generic;
  return (field ? e.errors[field]?.join(" ") : undefined) ?? e.detail;
}

function ObjectiveRow({
  objective,
  editable,
  onDontTest,
}: {
  objective: ObjectifAudit;
  editable: boolean;
  onDontTest: (o: ObjectifAudit) => void;
}) {
  const save = useSaveAuditObjective();
  const errorId = useId();
  const [draft, setDraft] = useState(objective.libelle ?? "");
  const [prev, setPrev] = useState(objective.libelle ?? "");
  const [error, setError] = useState<string | null>(null);
  if (prev !== (objective.libelle ?? "")) {
    setPrev(objective.libelle ?? "");
    setDraft(objective.libelle ?? "");
  }

  async function run(data: { libelle?: string; retenu?: boolean }) {
    setError(null);
    try {
      await save.mutateAsync({ id: objective.id, data });
    } catch (e) {
      setError(errorText(e, "libelle"));
    }
  }

  return (
    <TableRow>
      <TableCell className="font-medium">{objective.code}</TableCell>
      <TableCell className="min-w-64">
        {editable ? (
          <form
            className="flex items-start gap-2"
            onSubmit={(e) => {
              e.preventDefault();
              void run({ libelle: draft });
            }}
          >
            <div className="grid flex-1 gap-1">
              <Input
                aria-label={`${t.labelFor}${objective.code}`}
                aria-invalid={error !== null}
                aria-describedby={error ? errorId : undefined}
                value={draft}
                onChange={(e) => setDraft(e.target.value)}
              />
              {error && (
                <p id={errorId} role="alert" className="text-sm text-destructive">
                  {error}
                </p>
              )}
            </div>
            <Button
              type="submit"
              size="sm"
              variant="outline"
              disabled={draft === (objective.libelle ?? "") || save.isPending}
              aria-label={`${t.saveLabelFor}${objective.code}`}
            >
              {fr.common.save}
            </Button>
          </form>
        ) : (
          objective.libelle
        )}
      </TableCell>
      <TableCell>{objective.risque_code}</TableCell>
      <TableCell className="max-w-64">{objective.controle_existant || t.noControl}</TableCell>
      <TableCell>
        {objective.retenu ? (
          <span className="inline-flex items-center gap-1">
            <CheckCircle2 aria-hidden className="size-4" />
            {t.tested}
          </span>
        ) : (
          <span className="inline-flex items-center gap-1">
            <MinusCircle aria-hidden className="size-4" />
            {t.notTested}
            {objective.motif_non_test ? MOTIF_NON_TEST_LABELS[objective.motif_non_test] : ""}
          </span>
        )}
      </TableCell>
      {editable && (
        <TableCell>
          {objective.retenu ? (
            <Button
              type="button"
              size="sm"
              variant="outline"
              aria-label={`${t.dontTestFor}${objective.code}`}
              onClick={() => onDontTest(objective)}
            >
              {t.dontTest}
            </Button>
          ) : (
            <Button
              type="button"
              size="sm"
              variant="outline"
              disabled={save.isPending}
              aria-label={`${t.testFor}${objective.code}`}
              onClick={() => void run({ retenu: true })}
            >
              {t.test}
            </Button>
          )}
        </TableCell>
      )}
    </TableRow>
  );
}

export function ObjectivesTable({ missionId, editable }: { missionId: string; editable: boolean }) {
  const objectives = useAuditObjectives(missionId);
  const init = useInitializeObjectives();
  const save = useSaveAuditObjective();
  const [initError, setInitError] = useState<string | null>(null);
  const [target, setTarget] = useState<ObjectifAudit | null>(null);

  async function initialize() {
    setInitError(null);
    try {
      await init.mutateAsync({ missionId });
    } catch (e) {
      setInitError(errorText(e));
    }
  }

  if (objectives.isPending) return <p role="status">{fr.common.loading}</p>;
  if (objectives.isError)
    return (
      <p role="alert" className={ALERT_CLASS}>
        {fr.analyse.loadError}
      </p>
    );

  const rows = objectives.data.results;
  const initButton = editable && (
    <Button type="button" onClick={() => void initialize()} disabled={init.isPending}>
      {t.initialize}
    </Button>
  );

  return (
    <section aria-labelledby={`objectives-${missionId}`} className="grid gap-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <h4 id={`objectives-${missionId}`} className="font-semibold">
            {t.objectivesTitle}
          </h4>
          <p className="text-sm text-text-muted">{t.objectivesIntro}</p>
        </div>
        {rows.length > 0 && initButton}
      </div>
      {initError && (
        <p role="alert" className={ALERT_CLASS}>
          {initError}
        </p>
      )}
      {rows.length === 0 ? (
        <EmptyState title={t.emptyTitle} description={t.emptyText} illustration={false}>
          {initButton}
        </EmptyState>
      ) : (
        <Table aria-label={t.objectivesTable}>
          <TableHeader>
            <TableRow>
              <TableHead>{t.colCode}</TableHead>
              <TableHead>{t.colObjective}</TableHead>
              <TableHead>{t.colRisk}</TableHead>
              <TableHead>{t.colControl}</TableHead>
              <TableHead>{t.colDecision}</TableHead>
              {editable && <TableHead>{t.colActions}</TableHead>}
            </TableRow>
          </TableHeader>
          <TableBody>
            {rows.map((o) => (
              <ObjectiveRow key={o.id} objective={o} editable={editable} onDontTest={setTarget} />
            ))}
          </TableBody>
        </Table>
      )}
      <NonTestDialog
        objective={target}
        onOpenChange={(open) => {
          if (!open) setTarget(null);
        }}
        onSubmit={(o, values) =>
          save.mutateAsync({
            id: o.id,
            data: {
              retenu: false,
              motif_non_test: values.motif_non_test as keyof typeof MOTIF_NON_TEST_LABELS,
              justification: values.justification,
            },
          })
        }
      />
    </section>
  );
}
