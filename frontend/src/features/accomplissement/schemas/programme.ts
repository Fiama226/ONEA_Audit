import { z } from "zod";

/** Création d'un programme de travail : les deux textes sont facultatifs. */
export const programmeSchema = z.object({
  techniques: z.string(),
  criteres_preuve: z.string(),
});

export type ProgrammeFormValues = z.infer<typeof programmeSchema>;
