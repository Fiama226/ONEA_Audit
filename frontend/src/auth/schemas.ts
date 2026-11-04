import { z } from "zod";
import { fr } from "@/i18n/fr";

const T = fr.auth;

/** Same bounds as backend/apps/users/auth_serializers.py. */
export const IDENTIFIANT_MAX = 254;
export const MOT_DE_PASSE_MAX = 256;
/** Minimum length of a new password (Django MinimumLengthValidator). */
export const MOT_DE_PASSE_MIN = 12;

const identifiant = z.string().trim().min(1, T.identifiantRequired).max(IDENTIFIANT_MAX);
const code = z
  .string()
  .trim()
  .regex(/^\d{6}$/, T.otpFormat);
const nouveau = z.string().min(MOT_DE_PASSE_MIN, T.passwordTooShort).max(MOT_DE_PASSE_MAX);

export const loginSchema = z.object({
  identifiant,
  // Jamais rogné : les espaces font partie du mot de passe.
  mot_de_passe: z.string().min(1, T.passwordRequired).max(MOT_DE_PASSE_MAX),
});
export type LoginValues = z.infer<typeof loginSchema>;

export const otpSchema = z.object({ code });
export type OtpValues = z.infer<typeof otpSchema>;

export const forgotSchema = z.object({ identifiant });
export type ForgotValues = z.infer<typeof forgotSchema>;

export const resetSchema = z
  .object({ identifiant, code, nouveau_mot_de_passe: nouveau, confirmation: z.string() })
  .refine((v) => v.nouveau_mot_de_passe === v.confirmation, {
    message: T.passwordMismatch,
    path: ["confirmation"],
  });
export type ResetValues = z.infer<typeof resetSchema>;

export const changeSchema = z
  .object({
    ancien: z.string().min(1, T.currentPasswordRequired).max(MOT_DE_PASSE_MAX),
    nouveau,
    confirmation: z.string(),
  })
  .refine((v) => v.nouveau === v.confirmation, {
    message: T.passwordMismatch,
    path: ["confirmation"],
  });
export type ChangeValues = z.infer<typeof changeSchema>;
