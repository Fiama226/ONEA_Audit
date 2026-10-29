import { z } from "zod";
import { fr } from "@/i18n/fr";

const t = fr.analyseIII;

export const ANSWER_MAX = 5000;

export const answerSchema = z.object({
  appreciation: z.enum(["", "OUI", "NON", "SANS_OBJET"]),
  reponse: z.string().max(ANSWER_MAX, t.answerMax),
});
export type AnswerFormValues = z.infer<typeof answerSchema>;

export const newQuestionSchema = z.object({
  theme: z.string().trim().min(1, t.themeRequired).max(200, t.themeMax),
  libelle: z.string().trim().min(1, t.questionRequired).max(1000, t.questionMax),
});
export type NewQuestionFormValues = z.infer<typeof newQuestionSchema>;
