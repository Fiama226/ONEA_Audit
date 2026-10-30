import { useRef } from "react";
import { Link, useParams } from "react-router-dom";
import { isApiError } from "@/api/errors";
import { ALERT_CLASS } from "@/components/form/FormField";
import { Button } from "@/components/ui/button";
import { fr } from "@/i18n/fr";
import { usePlannedTests, useTestSheet } from "../api";
import { EvidenceList } from "../components/EvidenceList";
import { EvidenceUploader } from "../components/EvidenceUploader";
import { FicheStatusBadge } from "../components/FicheStatusBadge";
import { SheetActions } from "../components/SheetActions";
import { SheetForm, type SheetFormController } from "../components/SheetForm";
import { SheetJournal } from "../components/SheetJournal";
import type { FicheDetail } from "../types";

const t = fr.fiches;

function Header({ fiche }: { fiche: FicheDetail }) {
  const tests = usePlannedTests({ mission: fiche.mission });
  const test = tests.data?.results.find((item) => item.id === fiche.test);
  const sample = test
    ? [test.population, test.taille_echantillon ? `${test.taille_echantillon}` : ""]
        .filter(Boolean)
        .join(" · ")
    : "";
  const items: [string, string | undefined][] = [
    [t.objective, test?.objectif_test],
    [t.nature, test?.nature ? t.natures[test.nature] : undefined],
    [t.procedure, test?.procedure],
    [t.plannedSample, sample],
  ];
  return (
    <dl className="grid gap-2 text-sm sm:grid-cols-2" aria-busy={tests.isPending}>
      {items.map(([label, value]) => (
        <div key={label}>
          <dt className="font-medium">{label}</dt>
          <dd className="whitespace-pre-line text-text-muted">
            {tests.isError ? "—" : tests.isPending ? "…" : value || t.notProvided}
          </dd>
        </div>
      ))}
    </dl>
  );
}

/** Fiche de test (`/missions/:id/fiches/:ficheId`) : saisie, pièces, transitions et journal. */
export function FichePage() {
  const { ficheId } = useParams();
  const sheet = useTestSheet(ficheId);
  const controller = useRef<SheetFormController | null>(null);

  const title = (
    <h2 id="FichePage-title" className="text-lg font-semibold">
      {t.pageTitle}
    </h2>
  );
  if (sheet.isPending) {
    return (
      <section aria-labelledby="FichePage-title" className="grid gap-3">
        {title}
        <p role="status">{t.loading}</p>
      </section>
    );
  }
  if (sheet.isError) {
    const missing = isApiError(sheet.error) && sheet.error.status === 404;
    return (
      <section aria-labelledby="FichePage-title" className="grid gap-3">
        {title}
        <p role="alert" className={ALERT_CLASS}>
          {missing ? t.notFound : t.loadError}
        </p>
      </section>
    );
  }
  const fiche = sheet.data;
  const can = (action: string) => fiche.actions_possibles.includes(action);

  return (
    <article aria-labelledby="FichePage-title" className="grid gap-6">
      <header className="grid gap-3">
        <div className="flex flex-wrap items-center justify-between gap-2 print:hidden">
          <Link className="text-sm text-primary underline" to={`/missions/${fiche.mission}`}>
            {t.back}
          </Link>
          <Button type="button" variant="outline" size="sm" onClick={() => window.print()}>
            {t.print}
          </Button>
        </div>
        {title}
        <p className="text-base font-medium">
          {fiche.test_code} · {fiche.test_libelle}
        </p>{" "}
        <div className="flex flex-wrap items-center gap-3 text-sm">
          <FicheStatusBadge statut={fiche.statut} />
          <span className="text-text-muted">
            {t.auditor} : {fiche.auteur_detail.nom_complet}
          </span>
        </div>
        <Header fiche={fiche} />
      </header>
      {fiche.statut === "RENVOYE" && fiche.motif_renvoi && (
        <div role="alert" className={ALERT_CLASS}>
          <p className="font-medium">{t.returnReason}</p>
          <p>{t.returnReasonText(fiche.motif_renvoi)}</p>
        </div>
      )}
      <SheetForm fiche={fiche} editable={can("MODIFIER")} controllerRef={controller} />
      <section aria-labelledby="fiche-evidence" className="grid gap-3">
        <h3 id="fiche-evidence" className="text-base font-semibold">
          {t.evidenceTitle}
        </h3>
        {can("DEPOSER_PIECE") && (
          <div className="print:hidden">
            <EvidenceUploader ficheId={fiche.id} missionId={fiche.mission} />
          </div>
        )}
        <EvidenceList ficheId={fiche.id} missionId={fiche.mission} />
      </section>
      <SheetActions fiche={fiche} controller={controller} />
      <SheetJournal evenements={fiche.evenements} />
    </article>
  );
}
