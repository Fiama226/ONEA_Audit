import { zodResolver } from "@hookform/resolvers/zod";
import { useEffect, useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { isApiError } from "@/api/errors";
import { ALERT_CLASS, FormField } from "@/components/form/FormField";
import {
  AlertDialog,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { fr } from "@/i18n/fr";
import { useDraftResponseText, useRespondDraft } from "../api";
import type { ConstatProvisoire, RapportProvisoire } from "../types";
import { ConfirmationTextDialog } from "./ConfirmationTextDialog";

const t = fr.rapportProvisoire;

const schema = z.object({ commentaire: z.string().trim().min(1, t.commentRequired) });
type Values = z.infer<typeof schema>;

type Props = {
  provisoire: RapportProvisoire;
  constat: ConstatProvisoire;
  open: boolean;
  onOpenChange: (open: boolean) => void;
};

/** Réponse de l'audité : commentaire obligatoire, puis texte légal du serveur à confirmer. */
export function DraftResponseDialog({ provisoire, constat, open, onOpenChange }: Props) {
  if (!open) return null;
  return (
    <ResponseFlow provisoire={provisoire} constat={constat} onClose={() => onOpenChange(false)} />
  );
}

function ResponseFlow({
  provisoire,
  constat,
  onClose,
}: {
  provisoire: RapportProvisoire;
  constat: ConstatProvisoire;
  onClose: () => void;
}) {
  const [comment, setComment] = useState<string | null>(null);
  const [serverError, setServerError] = useState<string | null>(null);

  return (
    <>
      {comment === null && (
        <AlertDialog open onOpenChange={(next) => !next && onClose()}>
          <AlertDialogContent>
            <CommentForm
              title={t.responseTitle.replace("{reference}", constat.reference)}
              description={constat.titre}
              serverError={serverError}
              onClose={onClose}
              onNext={(value) => {
                setServerError(null);
                setComment(value);
              }}
            />
          </AlertDialogContent>
        </AlertDialog>
      )}
      {comment !== null && (
        <ConfirmStage
          provisoire={provisoire}
          constat={constat}
          comment={comment}
          onClose={onClose}
          onFieldError={(message) => {
            setServerError(message);
            setComment(null);
          }}
        />
      )}
    </>
  );
}
function CommentForm({
  title,
  description,
  serverError,
  onClose,
  onNext,
}: {
  title: string;
  description: string;
  serverError: string | null;
  onClose: () => void;
  onNext: (comment: string) => void;
}) {
  const {
    register,
    handleSubmit,
    setFocus,
    formState: { errors },
  } = useForm<Values>({ resolver: zodResolver(schema), defaultValues: { commentaire: "" } });
  useEffect(() => {
    if (serverError) setFocus("commentaire");
  }, [serverError, setFocus]);
  const message = errors.commentaire?.message ?? serverError ?? undefined;

  return (
    <form
      onSubmit={(e) => void handleSubmit((v) => onNext(v.commentaire.trim()))(e)}
      noValidate
      className="grid gap-4"
    >
      <AlertDialogHeader>
        <AlertDialogTitle>{title}</AlertDialogTitle>
        <AlertDialogDescription>{description}</AlertDialogDescription>
      </AlertDialogHeader>
      <FormField label={t.responseComment} error={message}>
        {(p) => <Textarea {...p} rows={4} {...register("commentaire")} />}
      </FormField>
      <AlertDialogFooter>
        <AlertDialogCancel type="button" onClick={onClose}>
          {fr.common.cancel}
        </AlertDialogCancel>
        <Button type="submit">{t.responseNext}</Button>
      </AlertDialogFooter>
    </form>
  );
}

function ConfirmStage({
  provisoire,
  constat,
  comment,
  onClose,
  onFieldError,
}: {
  provisoire: RapportProvisoire;
  constat: ConstatProvisoire;
  comment: string;
  onClose: () => void;
  onFieldError: (message: string) => void;
}) {
  const text = useDraftResponseText(provisoire.id, constat.id);
  const respond = useRespondDraft();
  const title = t.responseConfirmTitle.replace("{reference}", constat.reference);

  async function confirm() {
    try {
      const result = await respond.mutateAsync({
        missionId: provisoire.mission,
        data: {
          provisoire: provisoire.id,
          constat: constat.id,
          commentaire: comment,
          confirme: true,
        },
      });
      return result.confirmation;
    } catch (e) {
      const field = isApiError(e) ? e.errors.commentaire?.join(" ") : undefined;
      if (field) {
        onFieldError(field);
        return undefined;
      }
      throw e;
    }
  }

  if (text.data) {
    return (
      <ConfirmationTextDialog
        open
        onOpenChange={(next) => !next && onClose()}
        title={title}
        texte={text.data.texte}
        confirmLabel={t.responseConfirmLabel}
        onConfirm={confirm}
      />
    );
  }
  return (
    <AlertDialog open onOpenChange={(next) => !next && onClose()}>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>{title}</AlertDialogTitle>
          {text.isError ? (
            <AlertDialogDescription className="sr-only">{title}</AlertDialogDescription>
          ) : (
            <AlertDialogDescription role="status">{t.textLoading}</AlertDialogDescription>
          )}
        </AlertDialogHeader>
        {text.isError && (
          <p role="alert" className={ALERT_CLASS}>
            {t.textError}
          </p>
        )}
        <AlertDialogFooter>
          <AlertDialogCancel onClick={onClose}>{fr.common.close}</AlertDialogCancel>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}
