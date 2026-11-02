import { Download } from "lucide-react";
import { useState } from "react";
import { isApiError } from "@/api/errors";
import { Button } from "@/components/ui/button";
import { fr } from "@/i18n/fr";
import { exportAuditPlan } from "../api";

/** Export CSV / Excel du programme ; une erreur est affichée sans quitter la page. */
export function PlanExportButtons({ id }: { id: string }) {
  const p = fr.programmation;
  const c = fr.programmationPlans;
  const [pending, setPending] = useState<"csv" | "xlsx" | "pdf" | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function run(type: "csv" | "xlsx" | "pdf") {
    setPending(type);
    setError(null);
    try {
      await exportAuditPlan(id, type);
    } catch (e) {
      setError(isApiError(e) ? e.detail : c.exportError);
    } finally {
      setPending(null);
    }
  }

  return (
    <div className="print:hidden">
      <div role="group" aria-label={c.exportGroup} className="flex gap-2">
        <Button
          type="button"
          variant="outline"
          disabled={pending !== null}
          onClick={() => void run("csv")}
        >
          <Download aria-hidden />
          {p.exportCsv}
        </Button>
        <Button
          type="button"
          variant="outline"
          disabled={pending !== null}
          onClick={() => void run("xlsx")}
        >
          <Download aria-hidden />
          {p.exportXlsx}
        </Button>
        <Button
          type="button"
          variant="outline"
          disabled={pending !== null}
          onClick={() => void run("pdf")}
        >
          <Download aria-hidden />
          {p.exportPdf}
        </Button>
      </div>
      {pending && (
        <p role="status" className="mt-2 text-sm text-text-muted">
          {c.exporting}
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
