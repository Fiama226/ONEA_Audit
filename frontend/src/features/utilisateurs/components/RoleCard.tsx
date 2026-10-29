import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { fr } from "@/i18n/fr";
import { ROLE_LABELS } from "../labels";
import type { CompteUtilisateur } from "../types";

const t = fr.utilisateurs.fiche;

/** Rôle du compte : lecture seule, il appartient à l'annuaire (Keycloak). */
export function RoleCard({ account }: { account: CompteUtilisateur }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>{t.roleTitle}</CardTitle>
      </CardHeader>
      <CardContent className="grid gap-2 text-sm">
        <p className="font-medium">{ROLE_LABELS[account.role]}</p>
        <p className="text-text-muted">{t.roleNote}</p>
        {account.role_provisoire && <p className="text-warning-text">{t.roleProvisional}</p>}
      </CardContent>
    </Card>
  );
}
