import { ScrollText } from "lucide-react";
import { EmptyState } from "@/components/EmptyState";
import { fr } from "@/i18n/fr";
import { PageHeader } from "./preview";

export function DashboardAdmin() {
  return (
    <>
      <PageHeader title={fr.nav.dashboard} userRole="ADMIN" />
      <EmptyState
        title={fr.shell.adminTitle}
        description={fr.shell.adminText}
        action={{
          label: fr.dashboard.adminAction,
          icon: ScrollText,
          note: fr.dashboard.adminNote,
        }}
      />
    </>
  );
}
