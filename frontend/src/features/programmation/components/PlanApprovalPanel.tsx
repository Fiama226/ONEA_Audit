import { CheckCircle2, Clock } from "lucide-react";
import { useId, useState } from "react";
import { isApiError } from "@/api/errors";
import { useRole } from "@/auth/useRole";
import { ALERT_CLASS } from "@/components/form/FormField";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { t as gt } from "@/features/gouvernance/textes";
import { fr } from "@/i18n/fr";
import { formatDate } from "@/lib/dates";
import { useApproveAuditPlan } from "../api";
import type { AuditPlan } from "../types";

const t = gt.approval;

function ApprovalDialog({
  plan,
  niveau,
  onClose,
}: {
  plan: AuditPlan;
  niveau: "DG" | "BOARD";
  onClose: () => void;
}) {
  const id = useId();
  const approve = useApproveAuditPlan();
  const [date, setDate] = useState("");
  const [reference, setReference] = useState("");
  const [commentaire, setCommentaire] = useState("");
  const [error, setError] = useState<string | null>(null);
  const board = niveau === "BOARD";

  async function submit() {
    setError(null);
    try {
      await approve.mutateAsync({
        id: plan.id,
        niveau,
        date_decision: date || null,
        reference: reference.trim(),
        commentaire: commentaire.trim(),
      });
      onClose();
    } catch (e) {
      setError(
        isApiError(e)
          ? [e.detail, ...Object.values(e.errors).flat()]
              .filter((v, i, a) => a.indexOf(v) === i)
              .join(" ")
          : fr.errors.generic,
      );
    }
  }

  return (
    <Dialog open onOpenChange={(open) => !open && !approve.isPending && onClose()}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>{board ? t.boardTitle : t.dgTitle}</DialogTitle>
        </DialogHeader>
        <div className="grid gap-4">
          <div className="grid gap-1.5">
            <Label htmlFor={`${id}-date`}>{t.decisionDate}</Label>
            <Input
              id={`${id}-date`}
              type="date"
              value={date}
              onChange={(e) => setDate(e.target.value)}
            />
          </div>
          {board && (
            <div className="grid gap-1.5">
              <Label htmlFor={`${id}-ref`}>{t.reference}</Label>
              <Input
                id={`${id}-ref`}
                value={reference}
                maxLength={120}
                required
                onChange={(e) => setReference(e.target.value)}
              />
            </div>
          )}
          <div className="grid gap-1.5">
            <Label htmlFor={`${id}-com`}>{t.comment}</Label>
            <Textarea
              id={`${id}-com`}
              rows={3}
              value={commentaire}
              onChange={(e) => setCommentaire(e.target.value)}
            />
          </div>
          {error && (
            <p role="alert" className={ALERT_CLASS}>
              {error}
            </p>
          )}
        </div>
        <DialogFooter>
          <Button type="button" variant="outline" disabled={approve.isPending} onClick={onClose}>
            {fr.common.cancel}
          </Button>
          <Button type="button" disabled={approve.isPending} onClick={() => void submit()}>
            {t.confirm}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

/** Approbation du programme (règle de gouvernance) : état pour tous, saisie par le DG. */
export function PlanApprovalPanel({ plan }: { plan: AuditPlan }) {
  const { is } = useRole();
  const [open, setOpen] = useState<"DG" | "BOARD" | null>(null);
  const state = plan.approbation;
  const who = t.approvers[state.approbateur] ?? state.approbateur;
  const validated = plan.statut === "VALIDE";
  const next = state.manquantes[0];

  return (
    <section
      aria-labelledby="plan-approval-title"
      className="grid gap-2 rounded-lg border border-border bg-surface p-4 text-sm"
    >
      <h2 id="plan-approval-title" className="text-base font-semibold">
        {t.title}
      </h2>
      {!state.requise ? (
        <p className="text-text-muted">{t.notRequired}</p>
      ) : (
        <>
          <p className="text-text-muted">{t.required(who)}</p>
          {state.approbations.length > 0 && (
            <ul className="m-0 grid list-none gap-1 p-0">
              {state.approbations.map((a) => (
                <li key={a.niveau} className="flex items-start gap-2">
                  <CheckCircle2 className="mt-0.5 size-4 shrink-0 text-success" aria-hidden />
                  <span>
                    {t.line(
                      t.levels[a.niveau] ?? a.niveau_libelle,
                      a.approuve_par.nom_complet,
                      formatDate(a.date_decision),
                    )}
                    {a.reference && <span className="text-text-muted">{` · ${a.reference}`}</span>}
                    {a.commentaire && (
                      <span className="block text-text-muted">{a.commentaire}</span>
                    )}
                  </span>
                </li>
              ))}
            </ul>
          )}
          {!validated ? (
            <p className="text-text-muted">{t.draft}</p>
          ) : state.approuve ? (
            <p className="font-medium">{t.approved}</p>
          ) : (
            <p className="flex items-center gap-2">
              <Clock className="size-4 shrink-0 text-warning-text" aria-hidden />
              {t.pending(state.manquantes.map((n) => t.levels[n] ?? n).join(", "))}
            </p>
          )}
          {validated && next && is("DG") && (
            <div className="print:hidden">
              <Button type="button" size="sm" onClick={() => setOpen(next)}>
                {next === "BOARD" ? t.recordBoard : t.recordDg}
              </Button>
            </div>
          )}
        </>
      )}
      {open && <ApprovalDialog plan={plan} niveau={open} onClose={() => setOpen(null)} />}
    </section>
  );
}
