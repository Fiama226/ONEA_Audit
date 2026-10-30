import { useState } from "react";
import { useAuth } from "@/auth/useAuth";
import { NativeSelect } from "@/components/form/NativeSelect";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCaption,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { ConfirmActionDialog } from "@/features/missions/components/ConfirmActionDialog";
import { fr } from "@/i18n/fr";
import { formatDateTime } from "@/lib/dates";
import {
  useSignatureSettings,
  useUpdateSignatureSetting,
  type ModeSignature,
  type ParametreSignature,
} from "../adminApi";

const t = fr.signatureAdmin;
const ALL_MODES = Object.keys(t.modes) as ModeSignature[];

type Pending = { setting: ParametreSignature; mode: ModeSignature };

export function SignatureSettingsPage() {
  const query = useSignatureSettings();
  const update = useUpdateSignatureSetting();
  const { me } = useAuth();
  const isAdmin = me?.role === "ADMIN";
  const [pending, setPending] = useState<Pending | null>(null);

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
        <Skeleton className="h-32 w-full" />
      </div>
    );
  } else {
    body = (
      <Table>
        <TableCaption className="sr-only">{t.caption}</TableCaption>
        <TableHeader>
          <TableRow>
            <TableHead>{t.colType}</TableHead>
            <TableHead>{t.colMode}</TableHead>
            <TableHead>{t.colModifiedAt}</TableHead>
            <TableHead>{t.colModifiedBy}</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {query.data.map((s) => {
            const available = new Set(s.modes_disponibles.map((m) => m.mode));
            const hasUnavailable = ALL_MODES.some((m) => !available.has(m));
            const helpId = `sig-help-${s.type_document}`;
            return (
              <TableRow key={s.type_document}>
                <TableCell>{s.type_libelle}</TableCell>
                <TableCell>
                  {isAdmin ? (
                    <>
                      <NativeSelect
                        aria-label={t.selectLabel(s.type_libelle)}
                        aria-describedby={hasUnavailable ? helpId : undefined}
                        value={s.mode}
                        onChange={(e) =>
                          setPending({ setting: s, mode: e.target.value as ModeSignature })
                        }
                      >
                        {ALL_MODES.map((m) => (
                          <option key={m} value={m} disabled={!available.has(m) && m !== s.mode}>
                            {t.modes[m]}
                          </option>
                        ))}
                      </NativeSelect>
                      {hasUnavailable && (
                        <p id={helpId} className="mt-1 text-xs text-text-muted">
                          {t.unavailableHelp}
                        </p>
                      )}
                    </>
                  ) : (
                    s.mode_libelle
                  )}
                </TableCell>
                <TableCell>{s.modifie_le ? formatDateTime(s.modifie_le) : t.never}</TableCell>
                <TableCell>{s.modifie_par?.nom_complet ?? "—"}</TableCell>
              </TableRow>
            );
          })}
        </TableBody>
      </Table>
    );
  }

  return (
    <div className="grid gap-4">
      <div>
        <h1 className="text-2xl font-semibold">{t.title}</h1>
        <p className="mt-1 max-w-[70ch] text-sm text-text-muted">{t.help}</p>
        {!isAdmin && <p className="mt-1 text-sm text-text-muted">{t.readOnly}</p>}
      </div>
      {body}
      {pending && (
        <ConfirmActionDialog
          open
          onOpenChange={(open) => !open && setPending(null)}
          title={t.confirmTitle(pending.setting.type_libelle, t.modes[pending.mode])}
          text={t.confirmText}
          confirmLabel={t.confirmLabel}
          requireCheck={false}
          onConfirm={() =>
            update.mutateAsync({
              typeDocument: pending.setting.type_document,
              mode: pending.mode,
            })
          }
        />
      )}
    </div>
  );
}
