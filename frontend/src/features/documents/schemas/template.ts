import { z } from "zod";
import { fr } from "@/i18n/fr";

const t = fr.documentsAdmin;

/** Limite serveur (DOCUMENTS_MAX_GABARIT_MO) : inutile d'envoyer un fichier plus gros. */
export const MAX_TEMPLATE_MB = 10;
export const COMMENT_MAX_LENGTH = 500;

/** Message d'erreur (identique à celui du serveur) pour un fichier inacceptable, ou null. */
export function templateFileError(file: File | undefined): string | null {
  if (!file) return t.uploadFileRequired;
  const name = file.name.toLowerCase();
  if (name.endsWith(".doc")) return t.uploadDoc;
  if (!name.endsWith(".docx")) return t.uploadNotDocx;
  if (file.size > MAX_TEMPLATE_MB * 1024 * 1024) return t.uploadTooBig;
  return null;
}

export const templateSchema = z.object({
  fichier: z.custom<FileList | null>().superRefine((files, ctx) => {
    const message = templateFileError(files?.[0]);
    if (message) ctx.addIssue({ code: "custom", message });
  }),
  commentaire: z.string().max(COMMENT_MAX_LENGTH, t.uploadCommentMax),
});

export type TemplateFormValues = z.infer<typeof templateSchema>;
