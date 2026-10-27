import { useRole } from "@/auth/useRole";
import { DashboardAdmin } from "../components/DashboardAdmin";
import { DashboardAudite } from "../components/DashboardAudite";
import { DashboardAuditeur } from "../components/DashboardAuditeur";
import { DashboardDG } from "../components/DashboardDG";
import { DashboardRAI } from "../components/DashboardRAI";

/** Choisit le tableau de bord selon le rôle (statique dans ce lot : aucun appel réseau). */
export function DashboardPage() {
  const { role } = useRole();
  switch (role) {
    case "RAI":
      return <DashboardRAI />;
    case "AUDITEUR":
      return <DashboardAuditeur />;
    case "AUDITE":
      return <DashboardAudite />;
    case "DG":
      return <DashboardDG />;
    case "ADMIN":
      return <DashboardAdmin />;
    case null:
      return null;
  }
}
