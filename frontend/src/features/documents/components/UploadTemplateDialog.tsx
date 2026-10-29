import { zodResolver } from "@hookform/resolvers/zod";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { isApiError } from "@/api/errors";
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
import { Textarea } from "@/components/ui/textarea";
import { fr } from "@/i18n/fr";
import { useUploadTemplate } from "../api";
import { COMMENT_MAX_LENGTH, templateSchema, type TemplateFormValues } from "../schemas/template";

const t = fr.documentsAdmin;

type Props = { typeDocument: string; open: boolean; onOpenChange: (open: boolean) => void };

export function UploadTemplateDialog({ typeDocument, open, onOpenChange }: Props) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-lg">
        <UploadForm typeDocument={typeDocument} onClose={() => onOpenChange(false)} />
      </DialogContent>
    </Dialog>
  );
}

function UploadForm({ typeDocument, onClose }: { typeDocument: string; onClose: () => void }) {
  const upload = useUploadTemplate();
  const [problems, setProblems] = useState<string[]>([]);
  const [error, setError] = useState<string | null>(null);
  const {
    register,
    handleSubmit,
    setFocus,
    formState: { errors },
  } = useForm<TemplateFormValues>({
    resolver: zodResolver(templateSchema),
    defaultValues: { commentaire: "" },
  });

  async function onSubmit(values: TemplateFormValues) {
    if (upload.isPending) return;
    setProblems([]);
    setError(null);
    const file = values.fichier?.[0];
    if (!file) return;
    try {
      await upload.mutateAsync({
        type_document: typeDocument,
        fichier: file,
        commentaire: values.commentaire,
      });
      onClose();
    } catch (e) {
      if (!isApiError(e)) return setError(fr.errors.generic);
      const list = e.errors.fichier ?? [];
      if (list.length > 0) {
        setProblems(list);
        setFocus("fichier");
      } else {
        setError(e.detail);
      }
    }
  }

  const fileDescribedBy = problems.length > 0 ? "upload-problems" : undefined;

  return (
    <form onSubmit={(e) => void handleSubmit(onSubmit)(e)} noValidate className="grid gap-4">
      <DialogHeader>
        <DialogTitle>{t.uploadTitle}</DialogTitle>
        <DialogDescription>{t.uploadDescription}</DialogDescription>
      </DialogHeader>
      {error && (
        <p role="alert" className={ALERT_CLASS}>
          {error}
        </p>
      )}
      {problems.length > 0 && (
        <div role="alert" id="upload-problems" className={ALERT_CLASS}>
          <p className="font-medium">{t.uploadProblems}</p>
          <ul className="mt-1 list-disc pl-5">
            {problems.map((p) => (
              <li key={p}>{p}</li>
            ))}
          </ul>
        </div>
      )}
      <FormField label={t.uploadFile} help={t.uploadFileHelp} error={errors.fichier?.message}>
        {(p) => (
          <Input
            {...p}
            aria-describedby={
              [p["aria-describedby"], fileDescribedBy].filter(Boolean).join(" ") || undefined
            }
            type="file"
            accept=".docx,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            {...register("fichier")}
          />
        )}
      </FormField>
      <FormField label={t.uploadComment} error={errors.commentaire?.message}>
        {(p) => (
          <Textarea {...p} rows={3} maxLength={COMMENT_MAX_LENGTH} {...register("commentaire")} />
        )}
      </FormField>
      <DialogFooter>
        <Button type="button" variant="outline" onClick={onClose}>
          {fr.common.cancel}
        </Button>
        <Button type="submit" disabled={upload.isPending}>
          {upload.isPending ? t.uploadSubmitting : t.uploadSubmit}
        </Button>
      </DialogFooter>
    </form>
  );
}
