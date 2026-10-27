import type { ReactNode } from "react";
import { fr } from "@/i18n/fr";
import type { Role } from "./types";
import { useRole } from "./useRole";

export function RequireRole({ roles, children }: { roles: Role[]; children: ReactNode }) {
  const { is } = useRole();
  if (!is(...roles)) {
    return (
      <p role="alert" className="p-6 text-destructive">
        {fr.errors.forbidden}
      </p>
    );
  }
  return <>{children}</>;
}
