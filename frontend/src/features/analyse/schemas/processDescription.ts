import { z } from "zod";
import { fr } from "@/i18n/fr";

const t = fr.analyseIII;

const text = z.string().max(10000, t.textMax);

export const processDescriptionSchema = z.object({
  typologie: z.enum(["", "PILOTAGE", "SUPPORT", "REALISATION", "MESURE"]),
  categories_objectifs: z.array(
    z.enum(["OPERATIONNELS", "FIABILITE_INFORMATION", "STRATEGIQUES", "CONFORMITE"]),
  ),
  description: text,
  objectifs: text,
  indicateurs: text,
  sources: text,
  references_diagrammes: text,
});
export type ProcessDescriptionFormValues = z.infer<typeof processDescriptionSchema>;
