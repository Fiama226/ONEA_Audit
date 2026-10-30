import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom";
import { useRole } from "@/auth/useRole";
import { ALERT_CLASS } from "@/components/form/FormField";
import { useTestSheets } from "@/features/accomplissement/api";
import { useMission } from "@/features/missions/api";
import { fr } from "@/i18n/fr";
import { useFinding } from "../api";
import { ConstatForm } from "../components/ConstatForm";
import { ConstatStatusBadge } from "../components/ConstatStatusBadge";
import { ReponsesHistory } from "../components/ReponsesHistory";
import type { ConstatFormValues } from "../schemas/constat";

const t = fr.constatsUi;
const NEW = "nouveau";

/** Constat (`/missions/:id/constats/:constatId`) : édition, lecture seule ou création (« nouveau »). */
export function ConstatPage() {
  const { id, constatId } = useParams();
  const [search] = useSearchParams();
  const navigate = useNavigate();
  const { is } = useRole();
  const creating = constatId === NEW;
  // L'audité n'a pas accès aux fiches de test : il ne les charge pas.
  const audite = is("AUDITE");
  const mission = useMission(id);
  const sheets = useTestSheets({ mission: audite ? undefined : id });
  const finding = useFinding(creating ? undefined : constatId);
  const back = `/missions/${id}/constats`;

  if (mission.isError || (!audite && sheets.isError) || (!creating && finding.isError)) {
    return (
      <p role="alert" className={ALERT_CLASS}>
        {t.loadError}
      </p>
    );
  }
  if (!mission.data || (!audite && !sheets.data) || (!creating && !finding.data)) {
    return <p role="status">{fr.common.loading}</p>;
  }

  const constat = creating ? undefined : finding.data;
  const fiches = (sheets.data?.results ?? []).filter(
    (f) => f.statut === "VALIDE" && f.conclusion === "ANOMALIE",
  );
  const editable = creating
    ? mission.data.mes_droits.contribuer
    : (constat?.actions_possibles.includes("MODIFIER") ?? false);

  const prefill: Partial<ConstatFormValues> = {};
  if (creating) {
    const source = fiches.find((f) => f.id === search.get("fiche"));
    if (source) {
      prefill.fiches = [source.id];
      prefill.titre = source.test_libelle;
      prefill.fait_constate = source.resultat ?? "";
    }
    const [entite, ...autresEntites] = mission.data.entites_detail;
    const [processus, ...autresProcessus] = mission.data.processus_detail;
    if (entite && autresEntites.length === 0) prefill.entite = entite.id;
    if (processus && autresProcessus.length === 0) prefill.processus = processus.id;
  }

  const title = constat ? t.pageTitle.replace("{reference}", constat.reference) : t.pageTitleNew;
  return (
    <section aria-labelledby="constat-page-title" className="grid gap-6">
      <p className="hidden text-sm font-medium print:block">
        {t.printHeader} · {mission.data.reference} · {mission.data.titre}
      </p>
      <div className="grid gap-2 print:hidden">
        <Link to={back} className="text-sm text-primary underline">
          {t.back}
        </Link>
      </div>
      <div className="flex flex-wrap items-center gap-3">
        <h2 id="constat-page-title" className="text-lg font-semibold">
          {title}
        </h2>
        {constat && <ConstatStatusBadge statut={constat.statut} />}
      </div>
      {constat?.motif_renvoi && (
        <p role="note" className="rounded-md border border-border p-3 text-sm">
          {t.returnedReason.replace("{motif}", constat.motif_renvoi)}
        </p>
      )}
      <ConstatForm
        key={constat ? `${constat.id}-${constat.statut}-${constat.cycle}` : NEW}
        mission={mission.data}
        constat={constat}
        fiches={fiches}
        editable={editable}
        prefill={prefill}
        onSaved={(saved) => {
          if (creating) void navigate(`${back}/${saved.id}`, { replace: true });
        }}
        onDeleted={() => void navigate(`/missions/${id}/etapes/14`)}
      />
      {constat && <ReponsesHistory constatId={constat.id} />}
    </section>
  );
}
