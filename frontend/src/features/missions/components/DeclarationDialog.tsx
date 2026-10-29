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
import { formatDateTime } from "@/lib/dates";
import { useConfirmDeclaration, useDeclarations } from "../api";
import type { Declaration } from "../types";

const m = fr.missionPilotage;

type Props = {
  missionId: string;
  /** Monté seulement quand la boîte doit être ouverte : la déclaration est chargée à ce moment. */
  onClose: () => void;
};

/** « 3f2a…9c1b » : début et fin de l'empreinte SHA-256. */
export function shortHash(hash: string): string {
  return hash.length > 9 ? `${hash.slice(0, 4)}…${hash.slice(-4)}` : hash;
}

/** Déclaration d'indépendance de l'utilisateur connecté : texte serveur, confirmation ou situation déclarée. */
export function DeclarationDialog({ missionId, onClose }: Props) {
  const choiceId = useId();
  const descId = useId();
  const declarations = useDeclarations({ mission: missionId, mine: true });
  const confirm = useConfirmDeclaration();
  const [choice, setChoice] = useState<"confirm" | "conflict" | null>(null);
  const conflict = choice === "conflict";
  const [description, setDescription] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState<Declaration | null>(null);

  const declaration = declarations.data?.results.find((d) => d.statut === "EN_ATTENTE");

  async function submit() {
    if (!declaration || choice === null) return;
    if (conflict && description.trim() === "") {
      setError(m.declarationDescriptionRequired);
      return;
    }
    setError(null);
    try {
      setDone(
        await confirm.mutateAsync({
          id: declaration.id,
          conflit: conflict,
          description_conflit: conflict ? description.trim() : "",
        }),
      );
    } catch (e) {
      setError(
        isApiError(e) ? (e.errors.description_conflit?.join(" ") ?? e.detail) : fr.errors.generic,
      );
    }
  }

  const confirmation = done?.confirmation;
  let doneText = "";
  if (done && confirmation) {
    const [date = "", time = ""] = formatDateTime(confirmation.confirme_le).split(" ");
    doneText = (done.statut === "CONFLIT_DECLARE" ? m.declarationDoneConflict : m.declarationDone)
      .replace("{date}", date)
      .replace("{time}", time)
      .replace("{hash}", shortHash(confirmation.empreinte));
  }

  return (
    <AlertDialog
      open
      onOpenChange={(next) => {
        if (!next && !confirm.isPending) onClose();
      }}
    >
      <AlertDialogContent className="max-h-[90vh] overflow-y-auto">
        <AlertDialogHeader>
          <AlertDialogTitle>{m.declarationTitle}</AlertDialogTitle>
          <AlertDialogDescription asChild>
            <div>
              {declarations.isLoading && <p role="status">{fr.common.loading}</p>}
              {declarations.isError && <p>{m.declarationLoadError}</p>}
              {declarations.data && !declaration && !done && <p>{m.declarationNone}</p>}
              {declaration && !done && <p className="text-sm">{declaration.texte}</p>}
            </div>
          </AlertDialogDescription>
        </AlertDialogHeader>

        {done ? (
          <p role="status" className="text-sm" title={confirmation?.empreinte}>
            {doneText}
          </p>
        ) : (
          declaration && (
            <>
              <fieldset className="grid gap-2">
                <legend className="mb-1 text-sm font-medium">{m.declarationChoiceLegend}</legend>
                <label className="flex items-start gap-2 text-sm">
                  <input
                    type="radio"
                    name={choiceId}
                    className="mt-0.5 size-4 accent-primary"
                    checked={choice === "confirm"}
                    onChange={() => setChoice("confirm")}
                  />
                  {m.declarationConfirm}
                </label>
                <label className="flex items-start gap-2 text-sm">
                  <input
                    type="radio"
                    name={choiceId}
                    className="mt-0.5 size-4 accent-primary"
                    checked={conflict}
                    onChange={() => setChoice("conflict")}
                  />
                  {m.declarationConflict}
                </label>
              </fieldset>
              {conflict && (
                <div className="grid gap-1.5">
                  <Label htmlFor={descId}>{m.declarationDescription}</Label>
                  <Textarea
                    id={descId}
                    rows={4}
                    value={description}
                    onChange={(e) => setDescription(e.target.value)}
                    aria-invalid={error !== null}
                    required
                  />
                </div>
              )}
            </>
          )
        )}
        {error && (
          <p role="alert" className={ALERT_CLASS}>
            {error}
          </p>
        )}
        <AlertDialogFooter>
          {done ? (
            <Button type="button" onClick={onClose}>
              {m.close}
            </Button>
          ) : (
            <>
              <AlertDialogCancel disabled={confirm.isPending}>{fr.common.cancel}</AlertDialogCancel>
              {declaration && (
                <Button
                  type="button"
                  disabled={confirm.isPending || choice === null}
                  onClick={() => void submit()}
                >
                  {m.declarationSubmit}
                </Button>
              )}
            </>
          )}
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}
