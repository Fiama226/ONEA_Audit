import { Link, useLocation } from "react-router-dom";
import { fr } from "@/i18n/fr";
import { cn } from "@/lib/utils";

const TEMPLATES = "/administration/documents";
const NUMBERING = "/administration/documents/numerotation";

/** Navigation entre les écrans d'administration des documents (onglet exact, un seul actif). */
export function AdminTabs() {
  const { pathname } = useLocation();
  const numbering = pathname === NUMBERING || pathname === `${NUMBERING}/`;
  const links = [
    { to: TEMPLATES, label: fr.documents.tabTemplates, active: !numbering },
    { to: NUMBERING, label: fr.documents.tabNumbering, active: numbering },
  ];
  return (
    <nav aria-label={fr.documentsAdmin.navLabel}>
      <ul className="flex gap-4 border-b border-border">
        {links.map((l) => (
          <li key={l.to}>
            <Link
              to={l.to}
              aria-current={l.active ? "page" : undefined}
              className={cn(
                "inline-block border-b-2 px-1 pb-2 text-sm font-medium",
                l.active
                  ? "border-primary text-primary"
                  : "border-transparent text-text-muted hover:text-foreground",
              )}
            >
              {l.label}
            </Link>
          </li>
        ))}
      </ul>
    </nav>
  );
}
