import { ShieldAlert } from "lucide-react";
import { Link } from "react-router-dom";
import { fr } from "@/i18n/fr";

/** Panneau neutre « Accès refusé » : à rendre dans le conteneur de page (sans marge propre). */
export function ForbiddenView() {
  return (
    <>
      <h1 className="mb-6 text-2xl font-semibold tracking-[-0.012em]">
        {fr.errors.forbiddenTitle}
      </h1>
      <section
        role="status"
        className="flex max-w-[58ch] items-start gap-4 rounded-lg border border-border bg-surface px-6 py-6"
      >
        <ShieldAlert
          className="mt-0.5 size-5 shrink-0 text-text-muted"
          strokeWidth={1.5}
          aria-hidden
        />
        <div>
          <p className="text-sm">{fr.errors.forbiddenText}</p>
          <Link
            to="/"
            className="mt-3 inline-block text-sm font-medium text-primary underline-offset-[3px] hover:underline"
          >
            {fr.errors.backToDashboard}
          </Link>
        </div>
      </section>
    </>
  );
}
