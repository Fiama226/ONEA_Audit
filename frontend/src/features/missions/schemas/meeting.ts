import { z } from "zod";
import { fr } from "@/i18n/fr";

const t = fr.missionTravaux;

export const meetingSchema = z.object({
  date: z.string().min(1, t.dateRequired),
  lieu: z.string().max(200),
  ordre_du_jour: z.string(),
  participants: z.array(z.string()),
  participants_externes: z.string(),
  decisions: z.string(),
  compte_rendu: z.string(),
});

export type MeetingFormValues = z.infer<typeof meetingSchema>;
