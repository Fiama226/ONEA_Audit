import { AlertTriangle, CheckCircle2 } from "lucide-react";
import { Link } from "react-router-dom";
import { fr } from "@/i18n/fr";
import { useGovernanceRules } from "../api";
import { t } from "../textes";

/** Tableau de bord ADMIN et DG : état courant des règles de gouvernance assouplies. */
export function RelaxedRulesCard() {
  const query = useGovernanceRules();
  let body;
  if (query.isError) {
    body = <p className="text-sm text-text-muted">{t.relaxed.loadError}</p>;
  } else if (!query.data) {
    body = (
      <p role="status" className="text-sm text-text-muted">
        {fr.common.loading}
      </p>
    );
  } else {
    const relaxed = query.data
      .filter((r) => r.assouplie)
      .sort((a, b) => Number(b.issue_des_normes) - Number(a.issue_des_normes));
    body =
      relaxed.length === 0 ? (
        <p className="flex items-center gap-2 text-sm text-text-muted">
          <CheckCircle2 className="size-4 shrink-0 text-success" aria-hidden />
          {t.relaxed.none}
        </p>
      ) : (
        <ul className="m-0 grid list-none gap-1.5 p-0 text-sm">
          {relaxed.map((r) => (
            <li key={r.cle} className="flex items-start gap-2">
              <AlertTriangle className="mt-0.5 size-4 shrink-0 text-warning-text" aria-hidden />
              <span>
                <span className="font-medium">{r.libelle}</span>
                {r.issue_des_normes && (
                  <span className="text-text-muted">{` (${t.relaxed.norm})`}</span>
                )}
                {r.motif && <span className="block text-text-muted">{r.motif}</span>}
              </span>
            </li>
          ))}
        </ul>
      );
  }
  return (
    <section
      aria-labelledby="relaxed-rules"
      className="rounded-lg border border-border bg-surface p-4"
    >
      <div className="mb-2 flex flex-wrap items-baseline justify-between gap-2">
        <h2 id="relaxed-rules" className="text-base font-semibold">
          {t.relaxed.title}
        </h2>
        <Link
          to="/administration/gouvernance"
          className="text-sm text-primary underline underline-offset-2"
        >
          {t.relaxed.link}
        </Link>
      </div>
      {body}
    </section>
  );
}
