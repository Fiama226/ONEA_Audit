import type { ReactNode } from "react";
import { fr } from "@/i18n/fr";
import type { Role } from "./types";
import { useAuth } from "./useAuth";
import { useRole } from "./useRole";

export function RequireRole({ roles, children }: { roles: Role[]; children: ReactNode }) {
  const { status } = useAuth();
  const { is } = useRole();

  if (status === "loading") {
    return (
      <p role="status" className="p-6 text-muted-foreground">
        {fr.common.loading}
      </p>
    );
  }
  if (status !== "authenticated") return null;
  if (!is(...roles)) {
    return (
      <p role="alert" className="p-6 text-destructive">
        {fr.errors.forbidden}
      </p>
    );
  }
  return <>{children}</>;
}
