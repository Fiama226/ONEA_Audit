import { useEffect } from "react";
import { useLocation } from "react-router-dom";
import { fr } from "@/i18n/fr";
import { crumbsFor } from "./Breadcrumbs";

/** Titre d'onglet : page courante, puis sa section (« Constats - Missions »), puis l'application. */
export function documentTitleFor(pathname: string): string {
  const crumbs = crumbsFor(pathname).slice(1);
  const parts =
    crumbs.length === 0
      ? [fr.nav.dashboard]
      : crumbs
          .slice(-2)
          .reverse()
          .map((c) => c.label);
  return [...parts, fr.shell.appTitle].join(" - ");
}

/** Met à jour `document.title` à chaque navigation, pour distinguer les onglets ouverts. */
export function useDocumentTitle(): void {
  const { pathname } = useLocation();
  useEffect(() => {
    document.title = documentTitleFor(pathname);
  }, [pathname]);
}
