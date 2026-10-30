import { useEffect, useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { ALERT_CLASS, FormField } from "@/components/form/FormField";
import { fr } from "@/i18n/fr";
import { useDecideExtension, useRequestExtension } from "../api";
import { fieldErrorsOf, generalErrorOf } from "../serverErrors";
import type { ActionSuivie, DecisionReport, DemandeReport } from "../types";

const t = fr.suiviRegistre;

function frDate(iso: string): string {
  const [y = "", m = "", d = ""] = iso.split("-");
  return `${d}/${m}/${y}`;
}

type RequestErrors = { nouvelle_echeance?: string; motif?: string; general?: string };

function RequestForm({ action }: { action: ActionSuivie }) {
  const request = useRequestExtension();
  const [date, setDate] = useState("");
  const [motif, setMotif] = useState("");
  const [errors, setErrors] = useState<RequestErrors>({});
  const dateRef = useRef<HTMLInputElement>(null);
  const motifRef = useRef<HTMLTextAreaElement>(null);
  const [focus, setFocus] = useState<{ field: "date" | "motif"; n: number } | null>(null);

  useEffect(() => {
    if (focus?.field === "date") dateRef.current?.focus();
    if (focus?.field === "motif") motifRef.current?.focus();
  }, [focus]);

  function fail(next: RequestErrors) {
    setErrors(next);
    const field = next.nouvelle_echeance ? "date" : next.motif ? "motif" : null;
    if (field) setFocus((previous) => ({ field, n: (previous?.n ?? 0) + 1 }));
  }

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    const reason = motif.trim();
    const next: RequestErrors = {};
    if (!date) next.nouvelle_echeance = t.extensionDateRequired;
    // Comparaison de textes AAAA-MM-JJ : l'ordre lexicographique est l'ordre chronologique.
    else if (date <= action.echeance) {
      next.nouvelle_echeance = t.extensionDateAfter.replace("{date}", frDate(action.echeance));
    }
    if (!reason) next.motif = t.extensionReasonRequired;
    if (next.nouvelle_echeance || next.motif) return fail(next);
    setErrors({});
    try {
      await request.mutateAsync({ action: action.id, nouvelle_echeance: date, motif: reason });
      setDate("");
      setMotif("");
    } catch (error) {
      const fields = fieldErrorsOf(error);
      fail({
        nouvelle_echeance: fields.nouvelle_echeance,
        motif: fields.motif,
        general: generalErrorOf(error),
      });
    }
  }

  return (
    <form
      onSubmit={(e) => void submit(e)}
      noValidate
      aria-label={t.extensionRequest}
      className="grid gap-3 rounded-md border border-border p-4"
    >
      <FormField label={t.extensionDate} error={errors.nouvelle_echeance}>
        {(props) => (
          <Input
            {...props}
            ref={dateRef}
            type="date"
            value={date}
            onChange={(e) => setDate(e.target.value)}
          />
        )}
      </FormField>
      <FormField label={t.extensionReason} error={errors.motif}>
        {(props) => (
          <Textarea
            {...props}
            ref={motifRef}
            rows={3}
            value={motif}
            onChange={(e) => setMotif(e.target.value)}
          />
        )}
      </FormField>
      <div>
        <Button type="submit" disabled={request.isPending}>
          {t.extensionRequest}
        </Button>
      </div>
      {errors.general && (
        <p role="alert" className={ALERT_CLASS}>
          {errors.general}
        </p>
      )}
    </form>
  );
}

function Decision({ demande, actionId }: { demande: DemandeReport; actionId: string }) {
  const decide = useDecideExtension();
  const [comment, setComment] = useState("");
  const [error, setError] = useState<string>();
  const [fieldError, setFieldError] = useState<string>();
  const ref = useRef<HTMLTextAreaElement>(null);
  const [focus, setFocus] = useState(0);
  const possible = new Set(demande.actions_possibles);

  useEffect(() => {
    if (focus > 0) ref.current?.focus();
  }, [focus]);

  async function run(decision: DecisionReport) {
    setError(undefined);
    const text = comment.trim();
    if (decision === "refuse" && !text) {
      setFieldError(t.extensionRefuseRequired);
      setFocus((n) => n + 1);
      return;
    }
    setFieldError(undefined);
    try {
      await decide.mutateAsync({ id: demande.id, decision, commentaire: text, actionId });
      setComment("");
    } catch (e) {
      const fields = fieldErrorsOf(e);
      setFieldError(fields.commentaire);
      if (fields.commentaire) setFocus((n) => n + 1);
      setError(generalErrorOf(e) ?? t.extensionDecisionError);
    }
  }

  if (!possible.has("ACCEPTER") && !possible.has("REFUSER")) return null;
  return (
    <div className="grid gap-3">
      <FormField label={t.extensionDecisionComment} error={fieldError}>
        {(props) => (
          <Textarea
            {...props}
            ref={ref}
            rows={2}
            value={comment}
            onChange={(e) => setComment(e.target.value)}
          />
        )}
      </FormField>
      <div className="flex flex-wrap gap-2">
        {possible.has("ACCEPTER") && (
          <Button type="button" disabled={decide.isPending} onClick={() => void run("accept")}>
            {t.extensionAccept}
          </Button>
        )}
        {possible.has("REFUSER") && (
          <Button
            type="button"
            variant="outline"
            disabled={decide.isPending}
            onClick={() => void run("refuse")}
          >
            {t.extensionRefuse}
          </Button>
        )}
      </div>
      {error && (
        <p role="alert" className={ALERT_CLASS}>
          {error}
        </p>
      )}
    </div>
  );
}

/** Report d'échéance : demande par l'exécutant, décision par le RAI (droits du serveur). */
export function ExtensionPanel({ action }: { action: ActionSuivie }) {
  const pending = action.demande_report_en_attente;
  const canRequest = action.actions_possibles.includes("DEMANDER_REPORT") && pending === null;
  if (!pending && !canRequest) return null;
  return (
    <section
      aria-labelledby="extension-title"
      className="grid gap-3 rounded-lg border border-border p-5"
    >
      <h2 id="extension-title" className="text-base font-semibold">
        {t.extensionTitle}
      </h2>
      {pending && (
        <>
          <p className="text-sm">
            {t.extensionPending.replace("{date}", frDate(pending.nouvelle_echeance))} ·{" "}
            {t.extensionPendingBy.replace("{name}", pending.demandee_par.nom_complet)}
          </p>
          <p className="text-sm text-text-muted">{pending.motif}</p>
          <Decision demande={pending} actionId={action.id} />
        </>
      )}
      {canRequest && <RequestForm action={action} />}
    </section>
  );
}
