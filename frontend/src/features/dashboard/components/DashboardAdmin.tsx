import { FileText, FolderTree, PenLine, Users, type LucideIcon } from "lucide-react";
import { Link } from "react-router-dom";
import { useUserAccounts } from "@/features/utilisateurs/api";
import { fr } from "@/i18n/fr";
import { PageHeader } from "./preview";

const d = fr.dashboard;

type Shortcut = { to: string; label: string; hint: string; icon: LucideIcon };

const SHORTCUTS: Shortcut[] = [
  { to: "/administration/utilisateurs", label: d.adminUsers, hint: d.adminUsersHint, icon: Users },
  {
    to: "/administration/documents",
    label: d.adminTemplates,
    hint: d.adminTemplatesHint,
    icon: FileText,
  },
  {
    to: "/administration/signatures",
    label: d.adminSignature,
    hint: d.adminSignatureHint,
    icon: PenLine,
  },
  { to: "/referentiel", label: d.adminReferential, hint: d.adminReferentialHint, icon: FolderTree },
];

function PendingAccounts() {
  const pending = useUserAccounts({ en_attente_connexion: true, page_size: 1 });
  if (pending.isError) {
    return <p className="text-sm text-text-muted">{d.adminPendingError}</p>;
  }
  if (!pending.data) {
    return (
      <p role="status" className="text-sm text-text-muted">
        {fr.common.loading}
      </p>
    );
  }
  const count = pending.data.count;
  if (count === 0) return <p className="text-sm text-text-muted">{d.adminPendingNone}</p>;
  return (
    <p className="text-sm">
      <span className="font-medium">
        {count === 1 ? d.adminPendingOne : d.adminPendingMany.replace("{count}", String(count))}
      </span>
      {" · "}
      <Link
        to="/administration/utilisateurs?statut=attente"
        className="text-primary underline underline-offset-2"
      >
        {d.adminPendingLink}
      </Link>
    </p>
  );
}

export function DashboardAdmin() {
  return (
    <>
      <PageHeader title={fr.nav.dashboard} userRole="ADMIN" />
      <section aria-labelledby="admin-home" className="grid gap-6">
        <div>
          <h2 id="admin-home" className="text-xl font-semibold">
            {fr.shell.adminTitle}
          </h2>
          <p className="mt-1 max-w-2xl text-sm text-text-muted">{fr.shell.adminText}</p>
        </div>
        <PendingAccounts />
        <ul className="grid gap-4 sm:grid-cols-2">
          {SHORTCUTS.map(({ to, label, hint, icon: Icon }) => (
            <li key={to}>
              <Link
                to={to}
                className="flex h-full gap-3 rounded-lg border border-border bg-surface p-4 hover:bg-surface-subtle focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
              >
                <Icon className="mt-0.5 size-5 shrink-0 text-primary" aria-hidden />
                <span>
                  <span className="block font-medium">{label}</span>
                  <span className="block text-sm text-text-muted">{hint}</span>
                </span>
              </Link>
            </li>
          ))}
        </ul>
      </section>
    </>
  );
}
