import { zodResolver } from "@hookform/resolvers/zod";
import { useState } from "react";
import { Controller, useForm } from "react-hook-form";
import { applyApiErrors } from "@/api/formErrors";
import { ALERT_CLASS, FormField } from "@/components/form/FormField";
import { NativeSelect } from "@/components/form/NativeSelect";
import { ListIncompleteAlert } from "@/components/ListIncompleteAlert";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Textarea } from "@/components/ui/textarea";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { ConfirmActionDialog } from "@/features/missions/components/ConfirmActionDialog";
import { fr } from "@/i18n/fr";
import { useDeleteStrengthWeakness, useSaveStrengthWeakness, useStrengthsWeaknesses } from "../api";
import { TYPE_FORCE_FAIBLESSE_LABELS } from "../labels";
import {
  strengthWeaknessSchema,
  type StrengthWeaknessFormValues,
} from "../schemas/strengthWeakness";
import { Heading, type HeadingLevel } from "./Heading";
import type { ForceFaiblesse, TypeForceFaiblesse } from "../types";

const t = fr.analyseVVI;

type Props = { missionId: string; editable: boolean; level?: HeadingLevel };

type DialogState = { line?: ForceFaiblesse; type?: TypeForceFaiblesse } | null;

function SwForm({
  missionId,
  state,
  onDone,
}: {
  missionId: string;
  state: NonNullable<DialogState>;
  onDone: () => void;
}) {
  const save = useSaveStrengthWeakness();
  const line = state.line;
  const [formError, setFormError] = useState<string | null>(null);
  const {
    register,
    control,
    handleSubmit,
    setError,
    formState: { errors },
  } = useForm<StrengthWeaknessFormValues>({
    resolver: zodResolver(strengthWeaknessSchema),
    defaultValues: {
      type: line?.type ?? state.type ?? "",
      libelle: line?.libelle ?? "",
      consequence: line?.consequence ?? "",
      commentaire: line?.commentaire ?? "",
    },
  });

  async function onSubmit(values: StrengthWeaknessFormValues) {
    setFormError(null);
    if (values.type === "") return;
    const data = {
      mission: missionId,
      type: values.type,
      libelle: values.libelle,
      consequence: values.consequence,
      commentaire: values.commentaire,
    };
    try {
      if (line) {
        // Une ligne liée ne change pas de type (règle du serveur).
        const { type, ...rest } = data;
        await save.mutateAsync({ id: line.id, data: line.liee ? rest : { ...rest, type } });
      } else {
        await save.mutateAsync({ data });
      }
      onDone();
    } catch (e) {
      setFormError(applyApiErrors(e, setError, ["type", "libelle", "consequence", "commentaire"]));
    }
  }

  return (
    <form onSubmit={(e) => void handleSubmit(onSubmit)(e)} noValidate className="grid gap-4">
      <DialogHeader>
        <DialogTitle>{line ? t.swDialogTitleEdit : t.swDialogTitleAdd}</DialogTitle>
        <DialogDescription>{t.swDialogDesc}</DialogDescription>
      </DialogHeader>
      {formError && (
        <p role="alert" className={ALERT_CLASS}>
          {formError}
        </p>
      )}
      <Controller
        control={control}
        name="type"
        render={({ field }) => (
          <FormField
            label={t.typeLabel}
            error={errors.type?.message}
            help={line?.liee ? t.linkedHelp : undefined}
          >
            {(p) => (
              <NativeSelect
                {...p}
                required
                name={field.name}
                ref={field.ref}
                value={field.value}
                disabled={line?.liee === true}
                onBlur={field.onBlur}
                onChange={(e) => field.onChange(e.target.value)}
              >
                <option value="">{t.choose}</option>
                {(Object.keys(TYPE_FORCE_FAIBLESSE_LABELS) as TypeForceFaiblesse[]).map((k) => (
                  <option key={k} value={k}>
                    {TYPE_FORCE_FAIBLESSE_LABELS[k]}
                  </option>
                ))}
              </NativeSelect>
            )}
          </FormField>
        )}
      />
      <FormField label={t.wordingLabel} error={errors.libelle?.message}>
        {(p) => <Textarea {...p} rows={2} maxLength={500} required {...register("libelle")} />}
      </FormField>
      <FormField label={t.consequenceLabel} error={errors.consequence?.message}>
        {(p) => <Textarea {...p} maxLength={5000} rows={2} {...register("consequence")} />}
      </FormField>
      <FormField label={t.commentLabel} error={errors.commentaire?.message}>
        {(p) => <Textarea {...p} maxLength={5000} rows={2} {...register("commentaire")} />}
      </FormField>
      <DialogFooter>
        <Button type="button" variant="outline" onClick={onDone}>
          {fr.common.cancel}
        </Button>
        <Button type="submit" disabled={save.isPending}>
          {fr.common.save}
        </Button>
      </DialogFooter>
    </form>
  );
}

/** Forces et faiblesses apparentes ; les lignes issues de la MARC ne se retirent pas ici. */
export function StrengthsWeaknessesTable({ missionId, editable, level = 3 }: Props) {
  const list = useStrengthsWeaknesses(missionId);
  const remove = useDeleteStrengthWeakness();
  const [dialog, setDialog] = useState<DialogState>(null);
  const [deleting, setDeleting] = useState<ForceFaiblesse | null>(null);

  if (list.isError) {
    return (
      <div role="alert" className={ALERT_CLASS}>
        <p>{t.loadError}</p>
        <Button
          type="button"
          variant="outline"
          size="sm"
          className="mt-2"
          onClick={() => void list.refetch()}
        >
          {fr.common.retry}
        </Button>
      </div>
    );
  }
  if (list.isPending) {
    return (
      <p role="status" className="text-sm text-text-muted">
        {fr.common.loading}
      </p>
    );
  }
  const rows = list.data.results;

  const sections: { type: TypeForceFaiblesse; title: string; add: string }[] = [
    { type: "FORCE", title: t.strengths, add: t.addStrength },
    { type: "FAIBLESSE", title: t.weaknesses, add: t.addWeakness },
  ];

  return (
    <section aria-labelledby="sw-title" className="grid gap-4">
      <Heading level={level} id="sw-title" className="text-base font-semibold">
        {t.swTitle}
      </Heading>
      <ListIncompleteAlert count={list.data.count} loaded={rows.length} />
      {sections.map((s) => {
        const items = rows.filter((r) => r.type === s.type);
        const headingId = `sw-${s.type}`;
        return (
          <div key={s.type} className="grid gap-2">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <Heading
                level={(level + 1) as HeadingLevel}
                id={headingId}
                className="text-sm font-semibold"
              >
                {s.title}
              </Heading>
              {editable && (
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  className="print:hidden"
                  onClick={() => setDialog({ type: s.type })}
                >
                  {s.add}
                </Button>
              )}
            </div>
            <div className="overflow-x-auto rounded-md border border-border">
              <Table aria-labelledby={headingId} className="text-xs">
                <TableHeader>
                  <TableRow>
                    <TableHead>{t.colWording}</TableHead>
                    <TableHead>{t.colConsequence}</TableHead>
                    <TableHead>{t.colProcess}</TableHead>
                    <TableHead>{t.colComment}</TableHead>
                    {editable && (
                      <TableHead className="print:hidden">
                        <span className="sr-only">{fr.common.actions}</span>
                      </TableHead>
                    )}
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {items.length === 0 && (
                    <TableRow>
                      <TableCell colSpan={editable ? 5 : 4} className="text-text-muted">
                        {t.swEmpty}
                      </TableCell>
                    </TableRow>
                  )}
                  {items.map((r) => (
                    <TableRow key={r.id}>
                      <TableCell className="whitespace-normal">
                        {r.libelle}
                        {r.liee && (
                          <span className="ml-2 inline-flex h-5 items-center rounded-sm border border-border px-1.5 text-[11px] font-medium">
                            {t.fromMarc}
                          </span>
                        )}
                      </TableCell>
                      <TableCell className="whitespace-normal">{r.consequence || "—"}</TableCell>
                      <TableCell>{r.processus_code ?? "—"}</TableCell>
                      <TableCell className="whitespace-normal">{r.commentaire || "—"}</TableCell>
                      {editable && (
                        <TableCell className="print:hidden">
                          <div className="flex flex-wrap items-center gap-2">
                            <Button
                              type="button"
                              variant="outline"
                              size="sm"
                              aria-label={`${t.editSw} : ${r.libelle}`}
                              onClick={() => setDialog({ line: r })}
                            >
                              {fr.common.edit}
                            </Button>
                            <Button
                              type="button"
                              variant="outline"
                              size="sm"
                              disabled={r.liee}
                              aria-label={`${t.deleteSw} : ${r.libelle}`}
                              aria-describedby={r.liee ? `sw-help-${r.id}` : undefined}
                              onClick={() => setDeleting(r)}
                            >
                              {fr.common.delete}
                            </Button>
                            {r.liee && (
                              <span id={`sw-help-${r.id}`} className="text-text-muted">
                                {t.linkedHelp}
                              </span>
                            )}
                          </div>
                        </TableCell>
                      )}
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          </div>
        );
      })}
      {editable && dialog && (
        <Dialog open onOpenChange={(open) => !open && setDialog(null)}>
          <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-xl">
            <SwForm missionId={missionId} state={dialog} onDone={() => setDialog(null)} />
          </DialogContent>
        </Dialog>
      )}
      {editable && (
        <ConfirmActionDialog
          open={deleting !== null}
          onOpenChange={(open) => !open && setDeleting(null)}
          title={t.deleteSwTitle}
          text={t.deleteSwText}
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
