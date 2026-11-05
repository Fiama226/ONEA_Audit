import type { ReactNode } from "react";
import { LogoMark } from "@/components/Logo";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { fr } from "@/i18n/fr";

type Props = {
  title: string;
  /** Texte d'introduction sous le titre. */
  intro?: ReactNode;
  children: ReactNode;
  /** Liens secondaires sous le formulaire. */
  footer?: ReactNode;
};

/** Cadre commun des pages publiques de connexion et de mot de passe. */
export function AuthCard({ title, intro, children, footer }: Props) {
  // Même repère principal que la coque (#contenu) : cible commune des liens d'évitement.
  return (
    <main
      id="contenu"
      tabIndex={-1}
      className="mx-auto flex min-h-screen max-w-md items-center p-6 outline-none"
    >
      <Card className="w-full">
        <CardHeader className="justify-items-center text-center">
          <LogoMark className="mb-2 size-24" />
          <p className="text-sm font-medium text-text-muted">{fr.app.name}</p>
          <h1 className="text-xl font-semibold">{title}</h1>
          {intro && <div className="text-sm text-text-muted">{intro}</div>}
        </CardHeader>
        <CardContent className="grid gap-4">
          {children}
          {footer && <div className="grid gap-2 text-center text-sm">{footer}</div>}
        </CardContent>
      </Card>
    </main>
  );
}

/** Style des liens secondaires (charte : bleu primaire, soulignement au survol et au focus). */
export const AUTH_LINK_CLASS =
  "font-medium text-primary underline-offset-[3px] hover:underline focus-visible:underline";
