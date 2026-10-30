import { ALERT_CLASS } from "@/components/form/FormField";
import { fr } from "@/i18n/fr";
import { useReportPreview } from "../api";
import { SECTION_FIELDS } from "../schemas/report";

const t = fr.rapportFinal;

function asRecord(value: unknown): Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : {};
}

function text(value: unknown): string {
  return typeof value === "string" || typeof value === "number" ? String(value) : "";
}

/**
 * Assemblage du rapport en lecture, tel que le serveur le calcule à l'instant : non figé.
 * Le contenu s'imprime en A4 (le gabarit commun est posé par la page) et ne porte aucun bouton.
 */
export function ReportPreview({ rapportId }: { rapportId: string }) {
  const preview = useReportPreview(rapportId);
  if (preview.isError) {
    return (
      <p role="alert" className={ALERT_CLASS}>
        {t.previewLoadError}
      </p>
    );
  }
  if (!preview.data) {
    return (
      <p role="status" className="text-sm text-text-muted">
        {fr.common.loading}
      </p>
    );
  }
  const sections = asRecord(preview.data.sections);
  const constats = Array.isArray(preview.data.constats) ? preview.data.constats.map(asRecord) : [];

  return (
    <article aria-label={t.previewTitle} className="grid gap-4">
      <p className="rounded-md border border-border bg-muted px-3 py-2 text-sm font-medium print:hidden">
        {t.previewBanner}
      </p>
      {SECTION_FIELDS.map((field) => {
        const value = text(sections[field]);
        if (value === "") return null;
        return (
          <section key={field} className="grid gap-1 break-inside-avoid">
            <h4 className="text-sm font-semibold">{t.sections[field]}</h4>
            <p className="text-sm whitespace-pre-line">{value}</p>
          </section>
        );
      })}
      <section className="grid gap-2">
        <h4 className="text-sm font-semibold">
          {t.previewFindings.replace("{n}", String(constats.length))}
        </h4>
        {constats.length === 0 ? (
          <p className="text-sm text-text-muted">{t.previewNoFindings}</p>
        ) : (
          <ul className="grid gap-1 text-sm">
            {constats.map((c, i) => (
              <li key={text(c.reference) || i} className="break-inside-avoid">
                <span className="font-medium tabular-nums">{text(c.reference)}</span>{" "}
                {text(c.titre)}
                {text(c.entite) ? ` — ${text(c.entite)}` : ""}
              </li>
            ))}
          </ul>
        )}
      </section>
    </article>
  );
}
