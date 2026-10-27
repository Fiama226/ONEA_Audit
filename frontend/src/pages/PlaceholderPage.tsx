import { EmptyState } from "@/components/EmptyState";
import { fr } from "@/i18n/fr";

/** Page d'attente des sections ouvertes dans un prochain lot. */
export function PlaceholderPage({ title }: { title: string }) {
  return (
    <>
      <h1 className="mb-6 text-2xl font-semibold tracking-[-0.012em]">{title}</h1>
      <EmptyState
        title={fr.shell.comingSoonTitle}
        description={fr.shell.comingSoonText}
        illustration={false}
      />
    </>
  );
}
