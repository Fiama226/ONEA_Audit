import { useId, useState } from "react";
import { isApiError } from "@/api/errors";
import { ALERT_CLASS } from "@/components/form/FormField";
import {
  AlertDialog,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { fr } from "@/i18n/fr";
import { useArbitrateDeclaration, useDeclarations } from "../api";

const m = fr.missionPilotage;

type Props = { missionId: string; affectationId: string; onClose: () => void };

/** Arbitrage par le RAI d'une situation déclarée : l'auditeur reste affecté. */
export function ArbitrateDialog({ missionId, affectationId, onClose }: Props) {
  const id = useId();
  const declarations = useDeclarations({ mission: missionId });
  const arbitrate = useArbitrateDeclaration();
  const [justification, setJustification] = useState("");
  const [error, setError] = useState<string | null>(null);
  const declaration = declarations.data?.results.find((d) => d.affectation === affectationId);

  async function submit() {
    if (!declaration) return;
    const trimmed = justification.trim();
    if (trimmed === "") {
      setError(m.arbitrateRequired);
      return;
    }
    setError(null);
    try {
      await arbitrate.mutateAsync({ id: declaration.id, justification: trimmed });
      onClose();
    } catch (e) {
      setError(isApiError(e) ? (e.errors.justification?.join(" ") ?? e.detail) : fr.errors.generic);
    }
  }

  return (
    <AlertDialog
      open
      onOpenChange={(next) => {
        if (!next && !arbitrate.isPending) onClose();
      }}
    >
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>{m.arbitrateTitle}</AlertDialogTitle>
          <AlertDialogDescription>{m.arbitrateText}</AlertDialogDescription>
        </AlertDialogHeader>
        {declarations.isLoading && <p role="status">{fr.common.loading}</p>}
        {declarations.isError && <p className={ALERT_CLASS}>{m.declarationLoadError}</p>}
        {declaration && (
          <>
            <p className="text-sm">
              <span className="font-medium">{m.arbitrateSituation}</span>{" "}
              {declaration.description_conflit}
            </p>
            <div className="grid gap-1.5">
              <Label htmlFor={id}>{m.arbitrateJustification}</Label>
              <Textarea
                id={id}
                rows={4}
                required
                value={justification}
                onChange={(e) => setJustification(e.target.value)}
                aria-invalid={error !== null}
              />
            </div>
          </>
        )}
        {error && (
          <p role="alert" className={ALERT_CLASS}>
            {error}
          </p>
        )}
        <AlertDialogFooter>
          <AlertDialogCancel disabled={arbitrate.isPending}>{fr.common.cancel}</AlertDialogCancel>
          {declaration && (
            <Button type="button" disabled={arbitrate.isPending} onClick={() => void submit()}>
              {m.arbitrateConfirm}
            </Button>
          )}
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}
