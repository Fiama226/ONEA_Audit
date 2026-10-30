import { zodResolver } from "@hookform/resolvers/zod";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { applyApiErrors } from "@/api/formErrors";
import { ALERT_CLASS, FormField } from "@/components/form/FormField";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Textarea } from "@/components/ui/textarea";
import { fr } from "@/i18n/fr";
import { useSaveWorkProgram } from "../api";
import { METHODE_SELECTION_LABELS, NATURE_TEST_LABELS } from "../labels";
import { programmeSchema, type ProgrammeFormValues } from "../schemas/programme";
import type { ProgrammeTravail, TestPrevu } from "../types";

const t = fr.programme;
const MAX_PROCEDURE = 90;

export type ObjectiveRef = { id: string; code: string; libelle: string };

function abridged(text: string | undefined): string {
  const value = (text ?? "").trim();
  if (value === "") return t.notSet;
  return value.length > MAX_PROCEDURE ? `${value.slice(0, MAX_PROCEDURE).trimEnd()}…` : value;
}

function sample(test: TestPrevu): string {
  const parts = [
    test.taille_echantillon ? String(test.taille_echantillon) : "",
    test.methode_selection ? METHODE_SELECTION_LABELS[test.methode_selection] : "",
  ].filter(Boolean);
  return parts.length > 0 ? parts.join(" · ") : t.notSet;
}

type Props = {
  missionId: string;
  objective: ObjectiveRef;
  programme: ProgrammeTravail | undefined;
  tests: TestPrevu[];
  /** Création d'un programme autorisée (étape VIII ouverte). */
  canCreate: boolean;
  /** Ajout de tests : droit `MODIFIER_CONTENU` du programme, jamais recalculé. */
  onAddTest?: (programme: ProgrammeTravail, objective: ObjectiveRef) => void;
  /** Version imprimée : sans boutons d'écriture. */
  readOnly?: boolean;
};

/** Un objectif retenu, son programme (techniques, critères de preuve) et ses tests prévus. */
export function ProgrammeCard({
  missionId,
  objective,
  programme,
  tests,
  canCreate,
  onAddTest,
  readOnly = false,
}: Props) {
  const [creating, setCreating] = useState(false);
  const headingId = `programme-${objective.id}`;
  const canAddTest =
    !readOnly &&
    programme !== undefined &&
    programme.actions_possibles.includes("MODIFIER_CONTENU") &&
    onAddTest !== undefined;

  return (
    <section
      aria-labelledby={headingId}
      className="grid gap-3 rounded-md border border-border p-4 print:break-inside-avoid"
    >
      <div className="flex flex-wrap items-start justify-between gap-2">
        <h4 id={headingId} className="font-semibold">
          {t.objectiveTitle
            .replace("{code}", objective.code)
            .replace("{libelle}", objective.libelle)}
        </h4>
        {canAddTest && (
          <Button
            type="button"
            size="sm"
            variant="outline"
            aria-label={`${t.addTestFor}${objective.code}`}
            onClick={() => onAddTest(programme, objective)}
          >
            {t.addTest}
          </Button>
        )}
      </div>
      {programme === undefined ? (
        <div className="flex flex-wrap items-center justify-between gap-2">
          <p className="text-sm text-text-muted">{t.noProgram}</p>
          {canCreate && !readOnly && (
            <Button
              type="button"
              size="sm"
              aria-label={`${t.createProgramFor}${objective.code}`}
              onClick={() => setCreating(true)}
            >
              {t.createProgram}
            </Button>
          )}
        </div>
      ) : (
        <>
          <dl className="grid gap-2 text-sm sm:grid-cols-2">
            <div>
              <dt className="font-medium">{t.techniques}</dt>
              <dd className="whitespace-pre-line text-text-muted">
                {programme.techniques?.trim() || t.notSet}
              </dd>
            </div>
            <div>
              <dt className="font-medium">{t.criteria}</dt>
              <dd className="whitespace-pre-line text-text-muted">
                {programme.criteres_preuve?.trim() || t.notSet}
              </dd>
            </div>
          </dl>
          {tests.length === 0 ? (
            <p className="text-sm text-text-muted">{t.noTests}</p>
          ) : (
            <Table aria-label={t.testsCaption.replace("{code}", objective.code)}>
              <TableHeader>
                <TableRow>
                  <TableHead>{t.colCode}</TableHead>
                  <TableHead>{t.colLabel}</TableHead>
                  <TableHead>{t.colNature}</TableHead>
                  <TableHead>{t.colProcedure}</TableHead>
                  <TableHead>{t.colSample}</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {tests.map((test) => (
                  <TableRow key={test.id}>
                    <TableCell className="font-medium">{test.code}</TableCell>
                    <TableCell>
                      {test.libelle}
                      {test.statut === "ABANDONNE" && (
                        <span className="ml-2 text-text-muted">({t.abandoned})</span>
                      )}
                    </TableCell>
                    <TableCell>
                      {test.nature ? NATURE_TEST_LABELS[test.nature] : t.notSet}
                    </TableCell>
                    <TableCell className="max-w-72">{abridged(test.procedure)}</TableCell>
                    <TableCell>{sample(test)}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </>
      )}
      <Dialog open={creating} onOpenChange={setCreating}>
        <DialogContent>
          {creating && (
            <CreateProgramForm
              missionId={missionId}
              objective={objective}
              onDone={() => setCreating(false)}
            />
          )}
        </DialogContent>
      </Dialog>
    </section>
  );
}

const PROGRAM_FIELDS = ["techniques", "criteres_preuve"] as const;

function CreateProgramForm({
  missionId,
  objective,
  onDone,
}: {
  missionId: string;
  objective: ObjectiveRef;
  onDone: () => void;
}) {
  const save = useSaveWorkProgram();
  const [formError, setFormError] = useState<string | null>(null);
  const {
    register,
    handleSubmit,
    setError,
    formState: { errors, isSubmitting },
  } = useForm<ProgrammeFormValues>({
    resolver: zodResolver(programmeSchema),
    defaultValues: { techniques: "", criteres_preuve: "" },
  });

  async function submit(values: ProgrammeFormValues) {
    setFormError(null);
    try {
      await save.mutateAsync({
        missionId,
        data: {
          mission: missionId,
          objectif: objective.id,
          techniques: values.techniques.trim(),
          criteres_preuve: values.criteres_preuve.trim(),
        },
      });
      onDone();
    } catch (e) {
      setFormError(applyApiErrors(e, setError, PROGRAM_FIELDS));
    }
  }

  return (
    <form onSubmit={(e) => void handleSubmit(submit)(e)} noValidate className="grid gap-4">
      <DialogHeader>
        <DialogTitle>{t.createProgram}</DialogTitle>
        <DialogDescription>
          {t.createProgramFor}
          {objective.code}.
        </DialogDescription>
      </DialogHeader>
      {formError && (
        <p role="alert" className={ALERT_CLASS}>
          {formError}
        </p>
      )}
      <FormField label={t.techniques} error={errors.techniques?.message}>
        {(p) => <Textarea {...p} rows={3} {...register("techniques")} />}
      </FormField>
      <FormField label={t.criteria} error={errors.criteres_preuve?.message}>
        {(p) => <Textarea {...p} rows={3} {...register("criteres_preuve")} />}
      </FormField>
      <DialogFooter>
        <Button type="button" variant="outline" onClick={onDone}>
          {fr.common.cancel}
        </Button>
        <Button type="submit" disabled={isSubmitting}>
          {t.saveProgram}
        </Button>
      </DialogFooter>
    </form>
  );
}
