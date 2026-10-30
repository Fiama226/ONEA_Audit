import { fr } from "@/i18n/fr";

/** Squelette d'une zone de travail : titre accessible et mention de mise en place. */
export function ZoneSkeleton({ id, title }: { id: string; title: string }) {
  return (
    <section aria-labelledby={id} className="grid gap-2 rounded-md border border-border p-4">
      <h3 id={id} className="text-base font-semibold">
        {title}
      </h3>
      <p className="text-sm text-text-muted">{fr.accomplissement.zoneSoon}</p>
    </section>
  );
}
