import { fr } from "@/i18n/fr";
import { ConfirmDeleteDialog } from "@/features/referentiel/components/ConfirmDeleteDialog";

const s = fr.programmationLignes;

type Props = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onConfirm: () => Promise<unknown>;
};

/** Confirmation de suppression d'une mission prévue (programme en brouillon). */
export function DeleteLineDialog({ open, onOpenChange, onConfirm }: Props) {
  return (
    <ConfirmDeleteDialog
      open={open}
      onOpenChange={onOpenChange}
      title={s.deleteTitle}
      description={s.deleteText}
      onConfirm={onConfirm}
    />
  );
}
