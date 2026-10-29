import type { ReactNode } from "react";
import { Link, useParams } from "react-router-dom";
import { isApiError } from "@/api/errors";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { fr } from "@/i18n/fr";
import { formatDateTime } from "@/lib/dates";
import { useUserAccount } from "../api";
import { AccountStatusCard } from "../components/AccountStatusCard";
import { ProfileForm } from "../components/ProfileForm";
import { RoleCard } from "../components/RoleCard";
import { UserHistory } from "../components/UserHistory";
import { UserStatusBadge } from "../components/UserStatusBadge";
import { ORIGINE_LABELS } from "../labels";
import type { CompteUtilisateur } from "../types";

const t = fr.utilisateurs.fiche;

const LIST_PATH = "/administration/utilisateurs";

export function UserDetailPage() {
  const params = useParams();
  const id = Number(params.id);
  const query = useUserAccount(id);

  if (query.isPending) {
    return (
      <div role="status" aria-label={fr.common.loading} className="grid gap-4">
        <Skeleton className="h-8 w-64" />
        <Skeleton className="h-40 w-full" />
      </div>
    );
  }

  if (query.isError) {
    const notFound = isApiError(query.error) && query.error.status === 404;
    return (
      <div className="grid gap-3">
        <p role="alert">{notFound ? t.notFound : t.loadError}</p>
        <Link to={LIST_PATH} className="text-primary underline-offset-4 hover:underline">
          {t.backToList}
        </Link>
        {!notFound && (
          <div>
            <Button variant="outline" onClick={() => void query.refetch()}>
              {fr.common.retry}
            </Button>
          </div>
        )}
      </div>
    );
  }

  const account = query.data;
  return (
    <div className="grid gap-6">
      <header className="flex flex-wrap items-center gap-3">
        <div>
          <h1 className="text-2xl font-semibold">{account.nom_complet}</h1>
          <p className="text-sm text-text-muted">{account.username}</p>
        </div>
        <UserStatusBadge
          active={account.is_active}
          pendingFirstLogin={account.en_attente_connexion}
        />
      </header>
      <IdentityCard account={account} />
      <RoleCard account={account} />
      <ProfileForm account={account} />
      <AccountStatusCard account={account} />
      <UserHistory key={account.id} userId={account.id} />
    </div>
  );
}

function IdentityCard({ account }: { account: CompteUtilisateur }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>{t.identityTitle}</CardTitle>
      </CardHeader>
      <CardContent>
        <dl className="grid gap-x-6 gap-y-3 text-sm sm:grid-cols-2">
          <Item label={t.firstName}>{account.first_name}</Item>
          <Item label={t.lastName}>{account.last_name}</Item>
          <Item label={t.email}>{account.email}</Item>
          <Item label={t.directory}>
            {account.keycloak_lie ? t.directoryLinked : t.directoryNotLinked}
          </Item>
          <Item label={t.origin}>{ORIGINE_LABELS[account.origine]}</Item>
          <Item label={t.firstLogin}>
            {account.premiere_connexion_le
              ? `${t.firstLoginAt}${formatDateTime(account.premiere_connexion_le)}`
              : t.neverLoggedIn}
          </Item>
        </dl>
      </CardContent>
    </Card>
  );
}

function Item({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div>
      <dt className="text-text-muted">{label}</dt>
      <dd>{children}</dd>
    </div>
  );
}
