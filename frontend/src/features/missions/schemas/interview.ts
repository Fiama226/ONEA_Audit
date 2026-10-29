import { z } from "zod";
import { fr } from "@/i18n/fr";

const t = fr.missionTravaux;

export const interviewSchema = z.object({
  objet: z.string().trim().min(1, t.objectRequired).max(300, t.objectMax),
  date_prevue: z.string().min(1, t.dateRequired),
  duree_minutes: z
    .string()
    .trim()
    .refine(
      (v) => v === "" || (/^\d+$/.test(v) && Number(v) >= 1 && Number(v) <= 600),
      t.durationInvalid,
    ),
  lieu: z.string().max(200, t.lieuMax),
  etape: z.string(),
  auditeurs: z.array(z.string()),
  interlocuteurs: z.array(z.string()),
  autres_interlocuteurs: z.string(),
  themes: z.string(),
  compte_rendu: z.string(),
  note_synthese: z.string(),
});

export type InterviewFormValues = z.infer<typeof interviewSchema>;
