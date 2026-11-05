import { z } from "zod";
import { ROLES } from "@/auth/types";
import { fr } from "@/i18n/fr";

const t = fr.utilisateurs.fiche;
const c = fr.utilisateurs.creation;

/** Bornes de backend/apps/users/account_serializers.py. */
const name = z.string().trim().max(150, t.nameMax);
const email = z
  .string()
  .trim()
  .max(254, t.emailMax)
  .refine((v) => v === "" || z.email().safeParse(v).success, t.emailInvalid);
const matricule = z.string().trim().max(32, t.matriculeMax);
const fonction = z.string().trim().max(128, t.fonctionMax);

/**
 * Profil d'un compte. Le courriel n'est validé que s'il est modifiable et modifié : une
 * adresse déjà enregistrée (ou un champ grisé) ne bloque jamais l'enregistrement des autres.
 */
export function profileSchema({
  emailEditable,
  initialEmail,
}: {
  emailEditable: boolean;
  initialEmail: string;
}) {
  return z.object({
    first_name: name,
    last_name: name,
    email: z.string().superRefine((value, ctx) => {
      if (!emailEditable || value.trim() === initialEmail.trim()) return;
      const result = email.safeParse(value);
      if (!result.success) {
        ctx.addIssue({
          code: "custom",
          message: result.error.issues[0]?.message ?? t.emailInvalid,
        });
      }
    }),
    matricule,
    fonction,
    direction_code: z.string().trim(),
  });
}

export type ProfileFormValues = z.infer<ReturnType<typeof profileSchema>>;

export const deactivateSchema = z.object({
  motif: z.string().trim().min(1, t.reasonRequired).max(2000, t.reasonMax),
});

export type DeactivateFormValues = z.infer<typeof deactivateSchema>;

/** Même règle que le UnicodeUsernameValidator de Django. */
const USERNAME = /^[\p{L}\p{N}@.+\-_]+$/u;

/** « Nouvel agent » : rôle obligatoire, sans valeur par défaut (chaîne vide = non choisi). */
export const newAccountSchema = z.object({
  username: z
    .string()
    .trim()
    .min(1, c.usernameRequired)
    .max(150, c.usernameMax)
    .regex(USERNAME, c.usernameInvalid),
  first_name: name,
  last_name: name,
  email,
  role: z
    .string()
    .refine((v): v is (typeof ROLES)[number] => (ROLES as readonly string[]).includes(v), {
      message: c.roleRequired,
    }),
  matricule,
  direction_code: z.string().trim(),
  fonction,
  envoyer_courriel: z.boolean(),
});

export type NewAccountFormValues = z.input<typeof newAccountSchema>;
