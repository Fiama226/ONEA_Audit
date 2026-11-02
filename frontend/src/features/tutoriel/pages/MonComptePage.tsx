import { Button } from "@/components/ui/button";
import { useAuth } from "@/auth/useAuth";
import { fr } from "@/i18n/fr";
import { useTutoriel } from "../context";

const T = fr.tutoriel;

/** Profil de l'utilisateur connecté et relance de la visite guidée. */
export function MonComptePage() {
  const { me } = useAuth();
  const { relancer } = useTutoriel();
  if (!me) return null;
  const nom = `${me.first_name} ${me.last_name}`.trim() || me.username;
  const lignes: [string, string][] = [
    [T.accountName, nom],
    [T.accountEmail, me.email],
    [T.accountRole, fr.roles[me.role]],
    [T.accountDirection, me.direction_code],
    [T.accountFonction, me.fonction],
  ];
  return (
    <div className="max-w-2xl">
      <h1 className="text-2xl font-semibold">{T.accountTitle}</h1>
      <p className="mt-1 text-sm text-text-muted">{T.accountIntro}</p>
      <dl className="mt-6 grid grid-cols-[max-content_1fr] gap-x-6 gap-y-2 text-sm">
        {lignes.map(([libelle, valeur]) => (
          <div key={libelle} className="contents">
            <dt className="text-text-muted">{libelle}</dt>
            <dd>{valeur || "—"}</dd>
          </div>
        ))}
      </dl>
      <section aria-labelledby="visite-guidee" className="mt-8 border-t border-border pt-6">
        <h2 id="visite-guidee" className="text-base font-semibold">
          {T.tourSection}
        </h2>
        <p className="mt-1 text-sm text-text-muted">{T.tourSectionText}</p>
        <Button type="button" variant="outline" className="mt-4" onClick={relancer}>
          {T.replay}
        </Button>
      </section>
    </div>
  );
}
