import { useState, type RefObject } from "react";
import { isApiError } from "@/api/errors";
import { ALERT_CLASS } from "@/components/form/FormField";
import { Button } from "@/components/ui/button";
import { ConfirmActionDialog } from "@/features/missions/components/ConfirmActionDialog";
import { MotifDialog } from "@/features/missions/components/MotifDialog";
import { fr } from "@/i18n/fr";
import { useSheetAction } from "../api";
import type { FicheDetail } from "../types";
import type { SheetFormController } from "./SheetForm";

const t = fr.fiches;

type Dialog = "validate" | "return" | "reopen" | null;

type Props = {
  fiche: FicheDetail;
  controller: RefObject<SheetFormController | null>;
};

/** Transitions de la fiche ; seules les actions de `actions_possibles` sont proposées. */
export function SheetActions({ fiche, controller }: Props) {
  const action = useSheetAction();
  const [dialog, setDialog] = useState<Dialog>(null);
  const [error, setError] = useState<string | null>(null);
  const can = (name: string) => fiche.actions_possibles.includes(name);
  const base = { id: fiche.id, missionId: fiche.mission };

  async function submit() {
    setError(null);
    if (!(await controller.current?.prepareSubmit())) return;
    try {
      await action.mutateAsync({ ...base, action: "submit" });
    } catch (e) {
      setError(isApiError(e) ? e.detail : fr.errors.generic);
    }
  }

  if (!can("SOUMETTRE") && !can("VALIDER") && !can("RENVOYER") && !can("ROUVRIR")) return null;

  return (
    <div className="grid gap-2 print:hidden">
      {error && (
        <p role="alert" className={ALERT_CLASS}>
          {error}
        </p>
      )}
      <div className="flex flex-wrap gap-2">
        {can("SOUMETTRE") && (
          <Button type="button" disabled={action.isPending} onClick={() => void submit()}>
            {t.submit}
          </Button>
        )}
        {can("VALIDER") && (
          <Button type="button" onClick={() => setDialog("validate")}>
            {t.validate}
          </Button>
        )}
        {can("RENVOYER") && (
          <Button type="button" variant="outline" onClick={() => setDialog("return")}>
            {t.returnSheet}
          </Button>
        )}
        {can("ROUVRIR") && (
          <Button type="button" variant="outline" onClick={() => setDialog("reopen")}>
            {t.reopen}
          </Button>
        )}
      </div>
      <ConfirmActionDialog
        open={dialog === "validate"}
        onOpenChange={(open) => !open && setDialog(null)}
        title={t.validate}
        text={t.validateText}
        confirmLabel={t.validate}
        onConfirm={() => action.mutateAsync({ ...base, action: "validate" })}
      />
      <MotifDialog
        open={dialog === "return"}
        onOpenChange={(open) => !open && setDialog(null)}
        title={t.returnTitle}
        description={t.returnDescription}
        confirmLabel={t.returnSheet}
        onSubmit={(motif) => action.mutateAsync({ ...base, action: "return", motif })}
      />
      <MotifDialog
        open={dialog === "reopen"}
        onOpenChange={(open) => !open && setDialog(null)}
        title={t.reopenTitle}
        description={t.reopenDescription}
        confirmLabel={t.reopen}
        onSubmit={(motif) => action.mutateAsync({ ...base, action: "reopen", motif })}
      />
    </div>
  );
}
