import { useState } from "react";
import { isApiError } from "@/api/errors";
import { ALERT_CLASS } from "@/components/form/FormField";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { fr } from "@/i18n/fr";
import { formatDate, formatDateTime } from "@/lib/dates";
import { useMarkDelivered, useRecipients } from "../api";
import { CATEGORIE_DESTINATAIRE_LABELS } from "../labels";
import type { Destinataire } from "../types";
import { recipientName } from "./RecipientsEditor";

const t = fr.rapportFinal;

function when(iso: string | null) {
  return iso ? formatDateTime(iso) : <span className="text-text-muted">{t.notYet}</span>;
}

type Props = { rapportId: string; missionId: string; canMark?: boolean };

/** Suivi de la diffusion : notifié, consulté, accusé de réception et remise hors plateforme. */
export function DistributionTracking({ rapportId, missionId, canMark = false }: Props) {
  const recipients = useRecipients(rapportId);
  if (recipients.isError) {
    return (
      <p role="alert" className={ALERT_CLASS}>
        {t.recipientsError}
      </p>
    );
  }
  if (!recipients.data) {
    return (
      <p role="status" className="text-sm text-text-muted">
        {fr.common.loading}
      </p>
    );
  }
  return (
    <section aria-labelledby="tracking-title" className="grid gap-2">
      <h3 id="tracking-title" className="text-base font-semibold">
        {t.trackingTitle}
      </h3>
      {recipients.data.results.length === 0 ? (
        <p className="text-sm text-text-muted">{t.recipientsEmpty}</p>
      ) : (
        <table className="w-full text-sm">
          <caption className="sr-only">{t.trackingCaption}</caption>
          <thead>
            <tr className="border-b border-border text-left">
              <th scope="col" className="py-1 pr-3">
                {t.recipientName}
              </th>
              <th scope="col" className="py-1 pr-3">
                {t.notifiedOn}
              </th>
              <th scope="col" className="py-1 pr-3">
                {t.consultedOn}
              </th>
              <th scope="col" className="py-1 pr-3">
                {t.acknowledgedOn}
              </th>
              <th scope="col" className="py-1">
                {t.deliveredOn}
              </th>
            </tr>
          </thead>
          <tbody>
            {recipients.data.results.map((d) => (
              <tr key={d.id} className="border-b border-border align-top">
                <th scope="row" className="py-1 pr-3 text-left font-medium">
                  {recipientName(d)}
                  <span className="block text-xs font-normal text-text-muted">
                    {CATEGORIE_DESTINATAIRE_LABELS[d.categorie]}
                  </span>
                </th>
                <td className="py-1 pr-3 tabular-nums">{when(d.notifie_le)}</td>
                <td className="py-1 pr-3 tabular-nums">{when(d.premiere_consultation_le)}</td>
                <td className="py-1 pr-3 tabular-nums">{when(d.accuse_reception_le)}</td>
                <td className="py-1 tabular-nums">
                  {d.remis_hors_plateforme_le ? (
                    formatDate(d.remis_hors_plateforme_le)
                  ) : canMark && d.utilisateur === null ? (
                    <DeliveredForm recipient={d} missionId={missionId} />
                  ) : (
                    when(null)
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  );
}

function DeliveredForm({ recipient, missionId }: { recipient: Destinataire; missionId: string }) {
  const mark = useMarkDelivered();
  const [date, setDate] = useState(() => new Date().toISOString().slice(0, 10));
  const [error, setError] = useState<string | null>(null);

  async function submit() {
    setError(null);
    try {
      await mark.mutateAsync({ id: recipient.id, missionId, le: date });
    } catch (e) {
      setError(isApiError(e) ? e.detail : t.deliveredError);
    }
  }

  return (
    <div className="grid gap-1">
      <div className="flex flex-wrap items-center gap-2">
        <Input
          type="date"
          aria-label={t.deliveredDate.replace("{nom}", recipientName(recipient))}
          value={date}
          onChange={(e) => setDate(e.target.value)}
          className="w-40"
        />
        <Button
          type="button"
          size="sm"
          variant="outline"
          disabled={mark.isPending || !date}
          onClick={() => void submit()}
        >
          {t.markDelivered}
        </Button>
      </div>
      {error && (
        <p role="alert" className="text-xs text-destructive">
          {error}
        </p>
      )}
    </div>
  );
}
