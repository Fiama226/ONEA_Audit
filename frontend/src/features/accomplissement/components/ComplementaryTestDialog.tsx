import { zodResolver } from "@hookform/resolvers/zod";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { applyApiErrors } from "@/api/formErrors";
import { ALERT_CLASS, FormField } from "@/components/form/FormField";
import { NativeSelect } from "@/components/form/NativeSelect";
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
import { Textarea } from "@/components/ui/textarea";
import { fr } from "@/i18n/fr";
import { useSavePlannedTest } from "../api";
import { testComplementarySchema, type ComplementaryTestValues } from "../schemas/sheet";
import type { ProgrammeTravail, TestPrevuInput } from "../types";

const t = fr.fiches;
const FIELDS = ["programme", "libelle", "nature", "objectif_test"] as const;

type Props = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  missionId: string;
  /** Programmes pour lesquels l'ajout d'un test complémentaire est permis. */
  programs: ProgrammeTravail[];
};

export function ComplementaryTestDialog({ open, onOpenChange, ...rest }: Props) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-xl">
        <ComplementaryForm {...rest} onDone={() => onOpenChange(false)} />
      </DialogContent>
    </Dialog>
  );
}

function ComplementaryForm({
  missionId,
  programs,
  onDone,
}: Omit<Props, "open" | "onOpenChange"> & { onDone: () => void }) {
  const save = useSavePlannedTest();
  const [formError, setFormError] = useState<string | null>(null);
  const {
    register,
    handleSubmit,
    setError,
    formState: { errors },
  } = useForm<ComplementaryTestValues>({
    resolver: zodResolver(testComplementarySchema),
    defaultValues: {
      programme: programs.length === 1 ? (programs[0]?.id ?? "") : "",
      libelle: "",
      nature: "AUTRE",
      objectif_test: "",
    },
  });

  async function onSubmit(values: ComplementaryTestValues) {
    setFormError(null);
    try {
      await save.mutateAsync({
        missionId,
        data: {
          programme: values.programme,
          libelle: values.libelle,
          nature: values.nature as TestPrevuInput["nature"],
          objectif_test: values.objectif_test,
        },
      });
      onDone();
    } catch (e) {
      setFormError(applyApiErrors(e, setError, FIELDS));
    }
  }

  return (
    <form onSubmit={(e) => void handleSubmit(onSubmit)(e)} noValidate className="grid gap-4">
      <DialogHeader>
        <DialogTitle>{t.compTitle}</DialogTitle>
        <DialogDescription>{t.compDescription}</DialogDescription>
      </DialogHeader>
      {formError && (
        <p role="alert" className={ALERT_CLASS}>
          {formError}
        </p>
      )}
      <FormField label={t.compProgram} error={errors.programme?.message}>
        {(p) => (
          <NativeSelect {...p} required {...register("programme")}>
            <option value="">{t.compProgramChoose}</option>
            {programs.map((program) => (
              <option key={program.id} value={program.id}>
                {program.objectif_detail.code} · {program.objectif_detail.libelle}
              </option>
            ))}
          </NativeSelect>
        )}
      </FormField>
      <FormField label={t.compLabel} error={errors.libelle?.message}>
        {(p) => <Input {...p} required maxLength={300} {...register("libelle")} />}
      </FormField>
      <FormField label={t.compNature} error={errors.nature?.message}>
        {(p) => (
          <NativeSelect {...p} {...register("nature")}>
            {Object.entries(t.natures).map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </NativeSelect>
        )}
      </FormField>
      <FormField label={t.compObjective} error={errors.objectif_test?.message}>
        {(p) => <Textarea {...p} rows={3} {...register("objectif_test")} />}
      </FormField>
      <DialogFooter>
        <Button type="button" variant="outline" onClick={onDone}>
          {fr.common.cancel}
        </Button>
        <Button type="submit" disabled={save.isPending}>
          {t.compSave}
        </Button>
      </DialogFooter>
    </form>
  );
}
