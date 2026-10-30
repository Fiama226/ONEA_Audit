import {
  createElement,
  lazy,
  Suspense,
  type Attributes,
  type ComponentType,
  type ReactElement,
} from "react";
import { Skeleton } from "@/components/ui/skeleton";
import { fr } from "@/i18n/fr";

/** Repli affiché pendant le chargement d'un morceau de route (annoncé aux lecteurs d'écran). */
export function RouteFallback() {
  return (
    <div role="status" aria-live="polite" className="space-y-3">
      <span className="sr-only">{fr.common.loading}</span>
      <Skeleton className="h-8 w-1/3" />
      <Skeleton className="h-40 w-full" />
    </div>
  );
}

/**
 * Élément de route chargé à la demande : `lazyRoute(() => import("./pages/X"), "X", props)`.
 * À appeler une seule fois, à la déclaration des routes (module) : le morceau n'est
 * téléchargé qu'à la première visite de la route.
 */
export function lazyRoute<P extends object, K extends string>(
  load: () => Promise<Record<K, ComponentType<P>>>,
  name: K,
  props?: P,
): ReactElement {
  const Page = lazy<ComponentType<P>>(async () => ({ default: (await load())[name] }));
  return (
    <Suspense fallback={<RouteFallback />}>
      {createElement(Page, (props ?? {}) as P & Attributes)}
    </Suspense>
  );
}
