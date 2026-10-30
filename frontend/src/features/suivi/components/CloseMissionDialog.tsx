import { ConfirmActionDialog } from "@/features/missions/components/ConfirmActionDialog";
import { fr } from "@/i18n/fr";
import { useCloseMission } from "../api";

const t = fr.suiviRegistre;

type Props = {
  missionId: string;
  open: boolean;
  onOpenChange: (open: boolean) => void;
};

/** Clôture d'une mission : confirmation explicite (case jamais pré-cochée). */
export function CloseMissionDialog({ missionId, open, onOpenChange }: Props) {
  const close = useCloseMission();
  return (
    <ConfirmActionDialog
      open={open}
      onOpenChange={onOpenChange}
      title={t.missionCloseTitle}
      text={t.missionCloseText}
      confirmLabel={t.missionCloseConfirm}
      onConfirm={() => close.mutateAsync({ id: missionId })}
    />
  );
}
