import { Download } from "lucide-react";
import { useState } from "react";
import { isApiError } from "@/api/errors";
import { Button } from "@/components/ui/button";
import { fr } from "@/i18n/fr";
import { exportRiskMap } from "../api";

export function ExportButtons({ id }: { id: string }) {
  const [pending, setPending] = useState<"csv" | "xlsx" | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function run(type: "csv" | "xlsx") {
    setPending(type);
    setError(null);
    try {
      await exportRiskMap(id, type);
    } catch (e) {
      setError(isApiError(e) ? e.detail : fr.refCartographie.exportError);
    } finally {
      setPending(null);
    }
  }

  return (
    <div className="print:hidden">
      <div role="group" aria-label={fr.refCartographie.exportGroup} className="flex gap-2">
        <Button
          type="button"
          variant="outline"
          disabled={pending !== null}
          onClick={() => void run("csv")}
        >
          <Download aria-hidden />
          {fr.referentiel.exportCsv}
        </Button>
        <Button
          type="button"
          variant="outline"
          disabled={pending !== null}
          onClick={() => void run("xlsx")}
        >
          <Download aria-hidden />
          {fr.referentiel.exportXlsx}
        </Button>
      </div>
      {pending && (
        <p role="status" className="mt-2 text-sm text-text-muted">
          {fr.refCartographie.exporting}
        </p>
      )}
      {error && (
        <p role="alert" className="mt-2 text-sm text-destructive">
          {error}
        </p>
      )}
    </div>
  );
}
