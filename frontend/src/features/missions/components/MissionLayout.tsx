import { Link, Outlet, useLocation, useParams } from "react-router-dom";
import { isApiError } from "@/api/errors";
import { Skeleton } from "@/components/ui/skeleton";
import { fr } from "@/i18n/fr";
import { cn } from "@/lib/utils";
import { useMission } from "../api";
import { MissionHeader } from "./MissionHeader";

type Tab = { to: string; label: string; section: string; work: boolean };

/** Les onglets « travaux » exigent `voir_travaux` ; Réunions et Entretiens restent visibles. */
function tabsFor(currentStep: number): Tab[] {
  return [
    { to: `etapes/${currentStep}`, label: fr.missions.tabSteps, section: "etapes", work: true },
    { to: "equipe", label: fr.missions.tabTeam, section: "equipe", work: true },
    { to: "reunions", label: fr.missions.tabMeetings, section: "reunions", work: false },
    { to: "entretiens", label: fr.missions.tabInterviews, section: "entretiens", work: false },
    { to: "suivi", label: fr.missions.tabTracking, section: "suivi", work: true },
    {
      to: "referentiel-audit",
      label: fr.missions.tabAuditFramework,
      section: "referentiel-audit",
      work: false,
    },
    // Visible aussi pour l'audité (constats soumis) ; le serveur filtre le périmètre.
    { to: "constats", label: fr.missions.tabConstats, section: "constats", work: false },
  ];
}

/** Cadre d'une mission : en-tête, onglets, contenu de la page et panneau des documents. */
export function MissionLayout() {
  const { id } = useParams();
  const { pathname } = useLocation();
  const mission = useMission(id);

  if (mission.isLoading) {
    return (
      <div role="status" aria-label={fr.common.loading} className="grid gap-3">
        <Skeleton className="h-8 w-1/2" />
        <Skeleton className="h-24 w-full" />
      </div>
    );
  }
  if (mission.isError || !mission.data) {
    const notFound = isApiError(mission.error) && mission.error.status === 404;
    return (
      <p
        role="alert"
        className="rounded-md border border-destructive/40 p-3 text-sm text-destructive"
      >
        {notFound ? fr.missions.notFound : fr.errors.generic}
      </p>
    );
  }

  const data = mission.data;
  const seeWork = data.mes_droits.voir_travaux;
  const tabs = tabsFor(data.etape_courante?.numero ?? 1).filter((t) => seeWork || !t.work);
  const section = pathname.split(`/missions/${data.id}/`)[1]?.split("/")[0];

  return (
    <>
      <MissionHeader mission={data} />
      <nav aria-label={fr.missions.tabsLabel} className="mb-6 border-b border-border print:hidden">
        <ul className="-mb-px flex flex-wrap gap-x-6">
          {tabs.map((tab) => {
            const active = section === tab.section;
            return (
              <li key={tab.section}>
                <Link
                  to={`/missions/${data.id}/${tab.to}`}
                  aria-current={active ? "page" : undefined}
                  className={cn(
                    "inline-flex h-11 items-center border-b-2 text-sm font-medium focus-visible:outline-2 focus-visible:outline-ring",
                    active
                      ? "border-primary text-foreground"
                      : "border-transparent text-text-muted hover:text-foreground",
                  )}
                >
                  {tab.label}
                </Link>
              </li>
            );
          })}
        </ul>
      </nav>
      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_16rem]">
        <div className="min-w-0">
          <Outlet />
        </div>
        <aside
          aria-labelledby="mission-documents"
          className="h-fit rounded-md border border-border p-4 print:hidden"
        >
          <h2 id="mission-documents" className="mb-2 text-sm font-semibold">
            {fr.missions.documentsPanel}
          </h2>
          <p className="text-sm text-text-muted">{fr.missions.documentsSoon}</p>
        </aside>
      </div>
    </>
  );
}
