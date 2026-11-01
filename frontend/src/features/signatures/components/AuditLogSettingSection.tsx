import { useState } from "react";
import { useAuth } from "@/auth/useAuth";
import { NativeSelect } from "@/components/form/NativeSelect";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { ConfirmActionDialog } from "@/features/missions/components/ConfirmActionDialog";
import { fr } from "@/i18n/fr";
import { formatDateTime } from "@/lib/dates";
import { useAuditLogSetting, useUpdateAuditLogSetting, type ContenuJournal } from "../adminApi";

const t = fr.journalAuditAdmin;
const MODES = Object.keys(t.modes) as ContenuJournal[];

/** SEC-02 : contenu des missions visible par l'ADMIN dans la piste d'audit. */
export function AuditLogSettingSection() {
  const query = useAuditLogSetting();
  const update = useUpdateAuditLogSetting();
  const { me } = useAuth();
  const isAdmin = me?.role === "ADMIN";
  const [pending, setPending] = useState<ContenuJournal | null>(null);

  let body;
  if (query.isError) {
    body = (
      <div role="alert" className="rounded-lg border border-border bg-surface p-6 text-sm">
        <p>{t.loadError}</p>
        <Button
          type="button"
          variant="outline"
          className="mt-3"
          onClick={() => void query.refetch()}
        >
          {fr.common.retry}
        </Button>
      </div>
    );
  } else if (query.isLoading || !query.data) {
    body = (
      <div role="status" aria-label={fr.common.loading}>
        <Skeleton className="h-16 w-full" />
      </div>
    );
  } else {
    const s = query.data;
    body = (
      <div className="grid gap-2">
        {isAdmin ? (
          <NativeSelect
            aria-label={t.selectLabel}
            aria-describedby="journal-help"
            value={s.valeur}
            onChange={(e) => setPending(e.target.value as ContenuJournal)}
          >
            {MODES.map((m) => (
              <option key={m} value={m}>
                {t.modes[m]}
              </option>
            ))}
          </NativeSelect>
        ) : (
          <p>{t.modes[s.valeur]}</p>
        )}
        <p id="journal-help" className="text-xs text-text-muted">
          {t.modeHelp}
        </p>
        <p className="text-xs text-text-muted">
          {s.modifie_le && s.modifie_par
            ? t.modifiedBy(s.modifie_par.nom_complet, formatDateTime(s.modifie_le))
            : t.never}
        </p>
        {!isAdmin && <p className="text-sm text-text-muted">{t.readOnly}</p>}
      </div>
    );
  }

  return (
    <section aria-labelledby="journal-title" className="grid gap-3">
      <div>
        <h2 id="journal-title" className="text-xl font-semibold">
          {t.title}
        </h2>
        <p className="mt-1 max-w-[70ch] text-sm text-text-muted">{t.help}</p>
      </div>
      {body}
      {pending && (
        <ConfirmActionDialog
          open
          onOpenChange={(open) => !open && setPending(null)}
          title={t.confirmTitle(t.modes[pending])}
          text={t.confirmText}
          confirmLabel={t.confirmLabel}
          requireCheck={false}
          onConfirm={() => update.mutateAsync(pending)}
        />
      )}
    </section>
  );
}
