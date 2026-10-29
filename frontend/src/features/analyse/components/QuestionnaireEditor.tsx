import { zodResolver } from "@hookform/resolvers/zod";
import { useId, useState } from "react";
import { Controller, useForm } from "react-hook-form";
import { applyApiErrors } from "@/api/formErrors";
import { FormField, ALERT_CLASS } from "@/components/form/FormField";
import { NativeSelect } from "@/components/form/NativeSelect";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { ConfirmActionDialog } from "@/features/missions/components/ConfirmActionDialog";
import { fr } from "@/i18n/fr";
import { useDeleteQuestion, useQuestions, useSaveQuestion } from "../api";
import { APPRECIATION_LABELS, TYPE_QUESTIONNAIRE_LABELS } from "../labels";
import {
  answerSchema,
  newQuestionSchema,
  type AnswerFormValues,
  type NewQuestionFormValues,
} from "../schemas/questionnaire";
import type { Appreciation, Question, Questionnaire } from "../types";

const t = fr.analyseIII;

type Props = {
  questionnaire: Questionnaire;
  editable: boolean;
  /** Référence de la mission, affichée dans l'en-tête d'impression. */
  missionReference?: string;
};

function groupByTheme(questions: Question[]): [string, Question[]][] {
  const groups = new Map<string, Question[]>();
  for (const q of questions) groups.set(q.theme, [...(groups.get(q.theme) ?? []), q]);
  return [...groups.entries()];
}

export function QuestionnaireEditor({ questionnaire, editable, missionReference }: Props) {
  const questions = useQuestions(questionnaire.id);
  const writable = editable && !questionnaire.etape_close;

  if (questions.isPending) {
    return (
      <p role="status" className="text-sm text-text-muted">
        {fr.common.loading}
      </p>
    );
  }
  if (questions.isError) {
    return (
      <div role="alert" className={ALERT_CLASS}>
        <p>{t.loadError}</p>
        <Button type="button" variant="outline" size="sm" onClick={() => void questions.refetch()}>
          {fr.common.retry}
        </Button>
      </div>
    );
  }

  const list = [...questions.data.results].sort((a, b) => (a.ordre ?? 0) - (b.ordre ?? 0));
  const done = list.filter((q) => q.repondue).length;

  return (
    <div className="grid gap-4">
      <header className="hidden print:block">
        <h4 className="text-lg font-semibold">{TYPE_QUESTIONNAIRE_LABELS[questionnaire.type]}</h4>
        {missionReference && (
          <p className="text-sm">{t.missionRef.replace("{reference}", missionReference)}</p>
        )}
      </header>
      <p role="status" className="text-sm font-medium">
        {t.progress.replace("{done}", String(done)).replace("{total}", String(list.length))}
      </p>
      {list.length === 0 && <p className="text-sm text-text-muted">{t.noQuestion}</p>}
      {groupByTheme(list).map(([theme, items]) => (
        <section key={theme} className="grid gap-3" aria-label={theme}>
          <h5 className="text-sm font-semibold uppercase tracking-wide text-text-muted">{theme}</h5>
          {items.map((q) => (
            <QuestionRow
              key={q.id}
              question={q}
              missionId={questionnaire.mission}
              writable={writable}
            />
          ))}
        </section>
      ))}
      {writable && (
        <AddQuestionForm
          questionnaire={questionnaire}
          nextOrder={Math.max(-1, ...list.map((q) => q.ordre ?? 0)) + 1}
        />
      )}
    </div>
  );
}

function QuestionRow({
  question,
  missionId,
  writable,
}: {
  question: Question;
  missionId: string;
  writable: boolean;
}) {
  const save = useSaveQuestion();
  const remove = useDeleteQuestion();
  const [formError, setFormError] = useState<string | null>(null);
  const [removing, setRemoving] = useState(false);
  const {
    register,
    control,
    handleSubmit,
    setError,
    formState: { errors },
  } = useForm<AnswerFormValues>({
    resolver: zodResolver(answerSchema),
    defaultValues: {
      appreciation: question.appreciation ?? "",
      reponse: question.reponse ?? "",
    },
  });
  const uid = useId();
  const appreciationError = errors.appreciation?.message;
  const answerError = errors.reponse?.message;

  async function onSubmit(values: AnswerFormValues) {
    setFormError(null);
    try {
      await save.mutateAsync({ id: question.id, missionId, data: values });
    } catch (e) {
      setFormError(applyApiErrors(e, setError, ["appreciation", "reponse"]));
    }
  }

  return (
    <div className="grid gap-2 rounded-md border border-border p-3">
      <p className="text-sm font-medium">{question.libelle}</p>
      {writable ? (
        <form onSubmit={(e) => void handleSubmit(onSubmit)(e)} className="grid gap-2" noValidate>
          <div className="grid gap-1.5 sm:max-w-xs">
            <Controller
              control={control}
              name="appreciation"
              render={({ field }) => (
                <NativeSelect
                  {...field}
                  aria-label={t.appreciationOf.replace("{question}", question.libelle)}
                  aria-invalid={appreciationError !== undefined}
                  aria-describedby={appreciationError ? `${uid}-app` : undefined}
                >
                  <option value="">{t.notAnswered}</option>
                  {(Object.keys(APPRECIATION_LABELS) as Appreciation[]).map((a) => (
                    <option key={a} value={a}>
                      {APPRECIATION_LABELS[a]}
                    </option>
                  ))}
                </NativeSelect>
              )}
            />
            {appreciationError && (
              <p id={`${uid}-app`} className="text-sm text-destructive">
                {appreciationError}
              </p>
            )}
          </div>
          <div className="grid gap-1.5">
            <Textarea
              {...register("reponse")}
              aria-label={t.answerOf.replace("{question}", question.libelle)}
              aria-invalid={answerError !== undefined}
              aria-describedby={answerError ? `${uid}-rep` : undefined}
              maxLength={6000}
            />
            {answerError && (
              <p id={`${uid}-rep`} className="text-sm text-destructive">
                {answerError}
              </p>
            )}
          </div>
          {formError && (
            <p role="alert" className="text-sm text-destructive">
              {formError}
            </p>
          )}
          <div className="flex flex-wrap gap-2 print:hidden">
            <Button type="submit" size="sm" disabled={save.isPending}>
              {t.saveQuestion}
            </Button>
            <Button
              type="button"
              variant="outline"
              size="sm"
              aria-label={`${t.removeQuestion} : ${question.libelle}`}
              onClick={() => setRemoving(true)}
            >
              {t.removeQuestion}
            </Button>
          </div>
          <ConfirmActionDialog
            open={removing}
            onOpenChange={setRemoving}
            title={t.removeQuestionTitle}
            text={t.removeQuestionText.replace("{question}", question.libelle)}
            confirmLabel={t.removeQuestion}
            onConfirm={() =>
              remove.mutateAsync({
                id: question.id,
                missionId,
                questionnaireId: question.questionnaire,
              })
            }
          />
        </form>
      ) : (
        <p className="text-sm">
          <span className="font-medium">
            {question.appreciation
              ? APPRECIATION_LABELS[question.appreciation as Appreciation]
              : t.notAnswered}
          </span>
          {" — "}
          <span className="whitespace-pre-wrap">{question.reponse || t.noAnswer}</span>
        </p>
      )}
    </div>
  );
}

function AddQuestionForm({
  questionnaire,
  nextOrder,
}: {
  questionnaire: Questionnaire;
  nextOrder: number;
}) {
  const save = useSaveQuestion();
  const [formError, setFormError] = useState<string | null>(null);
  const {
    register,
    handleSubmit,
    setError,
    reset,
    formState: { errors },
  } = useForm<NewQuestionFormValues>({
    resolver: zodResolver(newQuestionSchema),
    defaultValues: { theme: "", libelle: "" },
  });

  async function onSubmit(values: NewQuestionFormValues) {
    setFormError(null);
    try {
      await save.mutateAsync({
        missionId: questionnaire.mission,
        data: { questionnaire: questionnaire.id, ordre: nextOrder, ...values },
      });
      reset();
    } catch (e) {
      setFormError(applyApiErrors(e, setError, ["theme", "libelle"]));
    }
  }

  return (
    <form
      onSubmit={(e) => void handleSubmit(onSubmit)(e)}
      className="grid gap-3 rounded-md border border-dashed border-border p-3 print:hidden"
      noValidate
    >
      <FormField label={t.theme} error={errors.theme?.message}>
        {(p) => <Input {...p} {...register("theme")} maxLength={200} />}
      </FormField>
      <FormField label={t.question} error={errors.libelle?.message}>
        {(p) => <Input {...p} {...register("libelle")} maxLength={1000} />}
      </FormField>
      {formError && (
        <p role="alert" className="text-sm text-destructive">
          {formError}
        </p>
      )}
      <div>
        <Button type="submit" variant="outline" size="sm" disabled={save.isPending}>
          {t.addQuestion}
        </Button>
      </div>
    </form>
  );
}
