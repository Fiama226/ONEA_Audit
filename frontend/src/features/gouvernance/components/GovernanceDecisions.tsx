import { useId, useState } from "react";
import { isApiError } from "@/api/errors";
import { useRole } from "@/auth/useRole";
import { ALERT_CLASS } from "@/components/form/FormField";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { fr } from "@/i18n/fr";
import {
  useDecideAcceptance,
  usePendingAcceptances,
  usePendingWaivers,
  useWaive,
  type PendingAcceptance,
  type PendingWaiver,
} from "../api";
import { RISK_LEVELS, t } from "../textes";

type Decision = { acceptance: PendingAcceptance; decision: "VALIDEE" | "REFUSEE" };

function ReasonDialog({
  title,
  description,
  confirmLabel,
  withReference,
  onSubmit,
  onClose,
}: {
  title: string;
  description?: string;
  confirmLabel: string;
  withReference: boolean;
  onSubmit: (motif: string, reference: string) => Promise<unknown>;
  onClose: () => void;
}) {
  const id = useId();
  const [motif, setMotif] = useState("");
  const [reference, setReference] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  async function submit() {
    setPending(true);
    setError(null);
    try {
      await onSubmit(motif.trim(), reference.trim());
      onClose();
    } catch (e) {
      setError(
        isApiError(e)
          ? [e.detail, ...Object.values(e.errors).flat()]
              .filter((v, i, a) => a.indexOf(v) === i)
              .join(" ")
          : fr.errors.generic,
      );
      setPending(false);
    }
  }

  return (
    <Dialog open onOpenChange={(open) => !open && !pending && onClose()}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>{title}</DialogTitle>
          {description && <DialogDescription>{description}</DialogDescription>}
        </DialogHeader>
        <div className="grid gap-4">
          {withReference && (
            <div className="grid gap-1.5">
              <Label htmlFor={`${id}-ref`}>{t.decisions.boardReference}</Label>
              <Input
                id={`${id}-ref`}
                value={reference}
                maxLength={120}
                onChange={(e) => setReference(e.target.value)}
              />
            </div>
          )}
          <div className="grid gap-1.5">
            <Label htmlFor={id}>{t.decisions.reason}</Label>
            <Textarea id={id} rows={3} value={motif} onChange={(e) => setMotif(e.target.value)} />
          </div>
          {error && (
            <p role="alert" className={ALERT_CLASS}>
              {error}
            </p>
          )}
        </div>
        <DialogFooter>
          <Button type="button" variant="outline" disabled={pending} onClick={onClose}>
            {fr.common.cancel}
          </Button>
          <Button type="button" disabled={pending} onClick={() => void submit()}>
            {confirmLabel}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function AcceptanceItem({
  acceptance,
  onDecide,
}: {
  acceptance: PendingAcceptance;
  onDecide: (d: Decision) => void;
}) {
  return (
    <li className="grid gap-1 border-b border-border py-2 last:border-b-0">
      <p className="font-medium">
        {t.decisions.acceptanceLine(
          acceptance.constat_reference,
          acceptance.mission_reference,
          RISK_LEVELS[acceptance.niveau_risque] ?? acceptance.niveau_risque,
        )}
      </p>
      <p className="text-text-muted">{acceptance.recommandation}</p>
      <p>
        <span className="text-text-muted">{`${t.decisions.justification} : `}</span>
        {acceptance.justification}
      </p>
      {acceptance.validation_requise === "BOARD" && (
        <p className="text-xs text-text-muted">{t.decisions.boardNote}</p>
      )}
      <div className="flex gap-2">
        <Button
          type="button"
          size="sm"
          onClick={() => onDecide({ acceptance, decision: "VALIDEE" })}
        >
          {t.decisions.validate}
        </Button>
        <Button
          type="button"
          size="sm"
          variant="outline"
          onClick={() => onDecide({ acceptance, decision: "REFUSEE" })}
        >
          {t.decisions.refuse}
        </Button>
      </div>
    </li>
  );
}

function WaiverItem({ waiver, onWaive }: { waiver: PendingWaiver; onWaive: () => void }) {
  return (
    <li className="grid gap-1 border-b border-border py-2 last:border-b-0">
      <p className="font-medium">
        {t.decisions.waiverLine(waiver.mission_reference, waiver.romain)}
        <span className="block font-normal text-text-muted">{waiver.mission_titre}</span>
      </p>
      <ul className="m-0 list-disc pl-5 text-text-muted">
        {waiver.manquants.map((m) => (
          <li key={m}>{m}</li>
        ))}
      </ul>
      <div>
        <Button type="button" size="sm" variant="outline" onClick={onWaive}>
          {t.decisions.waive}
        </Button>
      </div>
    </li>
  );
}

/** Tableau de bord RAI et DG : acceptations de risque à valider, dérogations attendues. */
export function GovernanceDecisions() {
  const { is } = useRole();
  const enabled = is("RAI", "DG");
  const acceptances = usePendingAcceptances(enabled);
  const waivers = usePendingWaivers(enabled);
  const decide = useDecideAcceptance();
  const waive = useWaive();
  const [decision, setDecision] = useState<Decision | null>(null);
  const [waiving, setWaiving] = useState<PendingWaiver | null>(null);

  if (!enabled) return null;
  const loading = acceptances.isLoading || waivers.isLoading;
  const failed = acceptances.isError || waivers.isError;
  const pendingAcceptances = acceptances.data ?? [];
  const pendingWaivers = waivers.data ?? [];

  return (
    <section
      aria-labelledby="governance-decisions"
      className="rounded-lg border border-border bg-surface p-4"
    >
      <h2 id="governance-decisions" className="mb-2 text-base font-semibold">
        {t.decisions.title}
      </h2>
      {failed ? (
        <p className="text-sm text-text-muted">{t.decisions.loadError}</p>
      ) : loading ? (
        <p role="status" className="text-sm text-text-muted">
          {fr.common.loading}
        </p>
      ) : pendingAcceptances.length + pendingWaivers.length === 0 ? (
        <p className="text-sm text-text-muted">{t.decisions.none}</p>
      ) : (
        <div className="grid gap-4 text-sm">
          {pendingAcceptances.length > 0 && (
            <div>
              <h3 className="font-semibold">{t.decisions.acceptances}</h3>
              <ul className="m-0 list-none p-0">
                {pendingAcceptances.map((a) => (
                  <AcceptanceItem key={a.id} acceptance={a} onDecide={setDecision} />
                ))}
              </ul>
            </div>
          )}
          {pendingWaivers.length > 0 && (
            <div>
              <h3 className="font-semibold">{t.decisions.waivers}</h3>
              <ul className="m-0 list-none p-0">
                {pendingWaivers.map((w) => (
                  <WaiverItem key={w.etape} waiver={w} onWaive={() => setWaiving(w)} />
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
      {decision && (
        <ReasonDialog
          title={
            decision.decision === "VALIDEE"
              ? t.decisions.validateTitle(decision.acceptance.constat_reference)
              : t.decisions.refuseTitle(decision.acceptance.constat_reference)
          }
          description={decision.decision === "REFUSEE" ? t.decisions.refuseHelp : undefined}
          confirmLabel={decision.decision === "VALIDEE" ? t.decisions.validate : t.decisions.refuse}
          withReference={decision.acceptance.validation_requise === "BOARD"}
          onSubmit={(motif, reference) =>
            decide.mutateAsync({
              id: decision.acceptance.id,
              decision: decision.decision,
              motif,
              reference_conseil: reference,
            })
          }
          onClose={() => setDecision(null)}
        />
      )}
      {waiving && (
        <ReasonDialog
          title={t.decisions.waiveTitle(waiving.mission_reference, waiving.romain)}
          description={t.decisions.waiveHelp}
          confirmLabel={t.decisions.waive}
          withReference={false}
          onSubmit={(motif) => waive.mutateAsync({ stepId: waiving.etape, motif })}
          onClose={() => setWaiving(null)}
        />
      )}
    </section>
  );
}
