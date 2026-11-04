import type { ReactNode } from "react";
import { ForbiddenView } from "@/components/ForbiddenView";
import { fr } from "@/i18n/fr";
import { useAccountRights } from "./useAccountRights";
import { useAuth } from "./useAuth";

/** Account administration: the ADMIN, or an agent holding at least one delegated right. */
export function RequireAccountManager({ children }: { children: ReactNode }) {
  const { status } = useAuth();
  const { canManage } = useAccountRights();

  if (status === "loading") {
    return (
      <p role="status" className="p-6 text-muted-foreground">
        {fr.common.loading}
      </p>
    );
  }
  if (status !== "authenticated") return null;
  if (!canManage) return <ForbiddenView />;
  return <>{children}</>;
}
