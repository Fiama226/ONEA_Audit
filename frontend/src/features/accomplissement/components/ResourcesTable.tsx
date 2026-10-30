import { zodResolver } from "@hookform/resolvers/zod";
import { useState } from "react";
import { Controller, useForm } from "react-hook-form";
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
import { Input } from "@/components/ui/input";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { useAllUsers } from "@/features/missions/api";
import { UserPicker } from "@/features/missions/components/UserPicker";
import { formatDays } from "@/features/missions/format";
import type { Affectation } from "@/features/missions/types";
import { fr } from "@/i18n/fr";
import { useSavePlannedTest } from "../api";
import { resourcesSchema, type ResourcesFormValues } from "../schemas/plannedTest";
import type { TestPrevu } from "../types";

const t = fr.programme;

const FIELDS = ["auditeur", "charge_prevue_jours", "date_debut_prevue", "date_fin_prevue"] as const;
const INTERVENANTS = ["CHEF_MISSION", "AUDITEUR", "SUPERVISEUR"];

/** « 2026-03-02 » -> « 02/03/2026 » (date calendaire, sans fuseau). */
function formatDay(value: string | null | undefined): string {
  if (!value) return t.notSet;
  const [y, m, d] = value.split("-");
  return `${d}/${m}/${y}`;
}

type Props = {
  missionId: string;
  equipe: Affectation[];
  tests: TestPrevu[];
  /** Étape IX ouverte et droit `MODIFIER_RESSOURCES` : jamais recalculé côté client. */
  editable: boolean;
};

/** Ressources prévues par test : auditeur, charge en jours, dates ; modifiables si autorisé. */
export function ResourcesTable({ missionId, equipe, tests, editable }: Props) {
  const [target, setTarget] = useState<TestPrevu | null>(null);

  if (tests.length === 0) {
    return <p className="text-sm text-text-muted">{t.noResourceTests}</p>;
  }

  return (
    <>
      <Table aria-label={t.resourcesCaption}>
        <TableHeader>
          <TableRow>
            <TableHead>{t.colCode}</TableHead>
            <TableHead>{t.colLabel}</TableHead>
            <TableHead>{t.colAuditor}</TableHead>
            <TableHead className="text-right">{t.colLoad}</TableHead>
            <TableHead>{t.colStart}</TableHead>
            <TableHead>{t.colEnd}</TableHead>
            {editable && <TableHead>{t.colActions}</TableHead>}
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
              <TableCell>{test.auditeur_detail?.nom_complet ?? t.unassigned}</TableCell>
              <TableCell className="text-right">{formatDays(test.charge_prevue_jours)}</TableCell>
              <TableCell>{formatDay(test.date_debut_prevue)}</TableCell>
              <TableCell>{formatDay(test.date_fin_prevue)}</TableCell>
              {editable && (
                <TableCell>
                  {test.actions_possibles.includes("MODIFIER") && (
                    <Button
                      type="button"
                      size="sm"
                      variant="outline"
                      aria-label={`${t.editResourcesFor}${test.code}`}
                      onClick={() => setTarget(test)}
                    >
                      {t.editResources}
                    </Button>
                  )}
                </TableCell>
              )}
            </TableRow>
          ))}
        </TableBody>
      </Table>
      <Dialog open={target !== null} onOpenChange={(open) => !open && setTarget(null)}>
        <DialogContent className="max-h-[90vh] overflow-y-auto">
          {target && (
            <ResourcesForm
              missionId={missionId}
              equipe={equipe}
              test={target}
              onDone={() => setTarget(null)}
            />
          )}
        </DialogContent>
      </Dialog>
    </>
  );
}

function ResourcesForm({
  missionId,
  equipe,
  test,
  onDone,
}: {
  missionId: string;
  equipe: Affectation[];
  test: TestPrevu;
  onDone: () => void;
}) {
  const save = useSavePlannedTest();
  const users = useAllUsers({});
  const [formError, setFormError] = useState<string | null>(null);
  const {
    register,
    control,
    handleSubmit,
    setError,
    formState: { errors, isSubmitting },
  } = useForm<ResourcesFormValues>({
    resolver: zodResolver(resourcesSchema),
    defaultValues: {
      auditeur: test.auditeur === null || test.auditeur === undefined ? "" : String(test.auditeur),
      charge_prevue_jours: test.charge_prevue_jours ?? "",
      date_debut_prevue: test.date_debut_prevue ?? "",
      date_fin_prevue: test.date_fin_prevue ?? "",
    },
  });

  const intervenants = equipe.filter((a) => INTERVENANTS.includes(a.role_mission));
  const allowed = new Set(intervenants.map((a) => String(a.utilisateur)));
  // Seuls les intervenants sont proposés ; le serveur reste seul juge (D13).
  const exclude = (users.data?.results ?? [])
    .map((u) => String(u.id))
    .filter((id) => !allowed.has(id));

  async function submit(values: ResourcesFormValues) {
    setFormError(null);
    try {
      await save.mutateAsync({
        missionId,
        id: test.id,
        data: {
          auditeur: values.auditeur === "" ? null : Number(values.auditeur),
          charge_prevue_jours:
            values.charge_prevue_jours.trim() === ""
              ? null
              : values.charge_prevue_jours.trim().replace(",", "."),
          date_debut_prevue: values.date_debut_prevue || null,
          date_fin_prevue: values.date_fin_prevue || null,
        },
      });
      onDone();
    } catch (e) {
      setFormError(applyApiErrors(e, setError, FIELDS));
    }
  }

  return (
    <form onSubmit={(e) => void handleSubmit(submit)(e)} noValidate className="grid gap-4">
      <DialogHeader>
        <DialogTitle>{t.resourcesDialogTitle}</DialogTitle>
        <DialogDescription>
          {test.code} : {test.libelle}
        </DialogDescription>
      </DialogHeader>
      {formError && (
        <p role="alert" className={ALERT_CLASS}>
          {formError}
        </p>
      )}
      <Controller
        control={control}
        name="auditeur"
        render={({ field }) => (
          <UserPicker
            single
            label={t.auditorPicker}
            value={field.value ? [field.value] : []}
            onChange={(ids) => field.onChange(ids[0] ?? "")}
            exclude={exclude}
            known={intervenants.map((a) => a.utilisateur_detail)}
            error={errors.auditeur?.message}
          />
        )}
      />
      <FormField label={t.loadField} error={errors.charge_prevue_jours?.message}>
        {(p) => <Input {...p} inputMode="decimal" {...register("charge_prevue_jours")} />}
      </FormField>
      <div className="grid gap-4 sm:grid-cols-2">
        <FormField label={t.startField} error={errors.date_debut_prevue?.message}>
          {(p) => <Input {...p} type="date" {...register("date_debut_prevue")} />}
        </FormField>
        <FormField label={t.endField} error={errors.date_fin_prevue?.message}>
          {(p) => <Input {...p} type="date" {...register("date_fin_prevue")} />}
        </FormField>
      </div>
      <DialogFooter>
        <Button type="button" variant="outline" onClick={onDone}>
          {fr.common.cancel}
        </Button>
        <Button type="submit" disabled={isSubmitting}>
          {t.saveResources}
        </Button>
      </DialogFooter>
    </form>
  );
}
