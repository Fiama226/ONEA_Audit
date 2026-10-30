import { useState } from "react";
import { MotifDialog } from "@/features/missions/components/MotifDialog";
import { Button } from "@/components/ui/button";
import { fr } from "@/i18n/fr";
import { useReportAction } from "../api";
import type { Rapport } from "../types";

const t = fr.rapportFinal;

/** « Émettre un rapport corrigé » : le motif est obligatoire (RAI, rapport diffusé). */
export function CorrectedReportDialog({ rapport }: { rapport: Rapport }) {
  const [open, setOpen] = useState(false);
  const action = useReportAction();
  return (
    <>
      <Button type="button" variant="outline" onClick={() => setOpen(true)}>
        {t.correct}
      </Button>
      <MotifDialog
        open={open}
        onOpenChange={setOpen}
        title={t.correctTitle}
        description={t.correctDescription}
        confirmLabel={t.correctConfirm}
        onSubmit={(motif) =>
          action.mutateAsync({
            id: rapport.id,
            missionId: rapport.mission,
            action: "correct",
            payload: { motif },
          })
        }
      />
    </>
  );
}
