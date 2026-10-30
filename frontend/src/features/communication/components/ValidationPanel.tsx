import { useState } from "react";
import { ALERT_CLASS } from "@/components/form/FormField";
import { Button } from "@/components/ui/button";
import { MotifDialog } from "@/features/missions/components/MotifDialog";
import { fr } from "@/i18n/fr";
import { useReportAction, useValidationText } from "../api";
import type { Rapport } from "../types";
import { ConfirmationTextDialog, type ConfirmationRecue } from "./ConfirmationTextDialog";

const t = fr.rapportFinal;

/**
 * Validation du rapport soumis (RAI seul, d'après `actions_possibles`) : mode de signature en
 * vigueur, validation par confirmation du texte exact du serveur (case jamais pré-cochée) et renvoi
 * motivé à l'équipe.
 */
export function ValidationPanel({ rapport }: { rapport: Rapport }) {
  const canValidate = rapport.actions_possibles.includes("VALIDER");
  const canReturn = rapport.actions_possibles.includes("RENVOYER");
  const text = useValidationText(canValidate ? rapport.id : undefined);
  const action = useReportAction();
  const [returning, setReturning] = useState(false);

  if (!canValidate && !canReturn) return null;

  async function validate(): Promise<ConfirmationRecue | void> {
    const result = await action.mutateAsync({
      id: rapport.id,
      missionId: rapport.mission,
      action: "validate",
      payload: { confirme: true },
    });
    const confirmation =
      "confirmation_validation" in result ? result.confirmation_validation : null;
    return confirmation ?? undefined;
  }

  return (
    <section
      aria-labelledby="validation-title"
      className="grid gap-3 rounded-md border border-border p-4"
    >
      <h3 id="validation-title" className="text-base font-semibold">
        {t.validationTitle}
      </h3>
      {text.data && (
        <p className="text-sm">
          <span className="text-text-muted">{t.signatureMode} : </span>
          <span className="font-medium">{t.modes[text.data.mode]}</span>
        </p>
      )}
      {canValidate && text.isError && (
        <p role="alert" className={ALERT_CLASS}>
          {t.validationTextError}
        </p>
      )}
      <div className="flex flex-wrap gap-2">
        {canValidate &&
          (text.data ? (
            <ConfirmationTextDialog
              title={t.validate}
              texte={text.data.texte}
              confirmLabel={t.validate}
              onConfirm={validate}
            >
              <Button type="button">{t.validate}</Button>
            </ConfirmationTextDialog>
          ) : (
            <Button type="button" disabled>
              {t.validate}
            </Button>
          ))}
        {canReturn && (
          <Button type="button" variant="outline" onClick={() => setReturning(true)}>
            {t.returnAction}
          </Button>
        )}
      </div>
      <MotifDialog
        open={returning}
        onOpenChange={setReturning}
        title={t.returnTitle}
        description={t.returnDescription}
        confirmLabel={t.returnConfirm}
        onSubmit={(motif) =>
          action.mutateAsync({
            id: rapport.id,
            missionId: rapport.mission,
            action: "return",
            payload: { motif },
          })
        }
      />
    </section>
  );
}
