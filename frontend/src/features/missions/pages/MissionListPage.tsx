import { Plus } from "lucide-react";
import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { useRole } from "@/auth/useRole";
import { DataTable, type DataTableColumn } from "@/components/DataTable";
import { EmptyState } from "@/components/EmptyState";
import { ALERT_CLASS } from "@/components/form/FormField";
import { NativeSelect } from "@/components/form/NativeSelect";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { currentYear } from "@/features/dashboard/year";
import { fr } from "@/i18n/fr";
import { formatDate } from "@/lib/dates";
import { useMissions, type MissionParams } from "../api";
import { MissionStatusBadge } from "../components/MissionStatusBadge";
import { PHASE_LABELS, STATUT_MISSION_LABELS, TYPE_MISSION_LABELS } from "../labels";
import type { MissionListe, StatutMission, TypeMission } from "../types";

const m = fr.missionPilotage;
const PAGE_SIZE = 20;
const DEBOUNCE_MS = 300;
const STATUSES = Object.keys(STATUT_MISSION_LABELS) as StatutMission[];
const TYPES = Object.keys(TYPE_MISSION_LABELS) as TypeMission[];

const date = (iso: string | null) => (iso ? formatDate(iso) : "-");

const COLUMNS: DataTableColumn<MissionListe>[] = [
  {
    id: "reference",
    accessorKey: "reference",
    header: fr.missions.colReference,
    cell: ({ row }) => (
      <Link
        to={row.original.id}
        className="font-medium text-primary underline-offset-[3px] hover:underline focus-visible:outline-2 focus-visible:outline-ring"
      >
        {row.original.reference || fr.missions.draft}
      </Link>
    ),
  },
  {
    id: "titre",
    header: fr.missions.colTitle,
    enableSorting: false,
    cell: ({ row }) => (
      <span>
        {row.original.titre}
        {row.original.ma_declaration_en_attente && (
          <span className="ml-2 inline-flex items-center rounded-full border border-warning/50 px-2 py-0.5 text-xs font-medium text-warning-text">
            {m.pendingDeclaration}
          </span>
        )}
      </span>
    ),
  },
  {
    id: "type",
    header: fr.missions.colType,
    enableSorting: false,
    cell: ({ row }) => TYPE_MISSION_LABELS[row.original.type],
  },
  {
    id: "statut",
    header: fr.missions.colStatus,
    enableSorting: false,
    cell: ({ row }) => <MissionStatusBadge statut={row.original.statut} />,
  },
  {
    id: "phase",
    header: fr.missions.colPhase,
    enableSorting: false,
    cell: ({ row }) => (row.original.phase ? PHASE_LABELS[row.original.phase] : "-"),
  },
  {
    id: "chef",
    header: fr.missions.colChief,
    enableSorting: false,
    cell: ({ row }) => row.original.chef_mission?.nom_complet ?? "-",
  },
  {
    id: "date_debut_prevue",
    accessorKey: "date_debut_prevue",
    header: m.colStart,
    cell: ({ row }) => date(row.original.date_debut_prevue),
  },
  {
    id: "date_fin_prevue",
    header: m.colEnd,
    enableSorting: false,
    cell: ({ row }) => date(row.original.date_fin_prevue),
  },
];

export function MissionListPage() {
  const { is } = useRole();
  const isRai = is("RAI");
  const [params, setParams] = useSearchParams();
  const q = (params.get("q") ?? "").slice(0, 100);
  const rawStatut = params.get("statut") ?? "";
  const statut = (STATUSES as string[]).includes(rawStatut) ? rawStatut : "";
  const rawType = params.get("type") ?? "";
  const type = (TYPES as string[]).includes(rawType) ? rawType : "";
  const rawAnnee = params.get("annee") ?? "";
  const annee = /^[0-9]{4}$/.test(rawAnnee) ? rawAnnee : "";
  const ordering = params.get("ordering") ?? "";
  const page = Math.max(1, Number(params.get("page")) || 1);

  const [search, setSearch] = useState(q);
  // Retour/avance du navigateur : la saisie suit le paramètre d'URL.
  const [seenQ, setSeenQ] = useState(q);
  if (q !== seenQ) {
    setSeenQ(q);
    // Ne pas écraser la saisie en cours (espace final) quand l'URL vient de l'anti-rebond.
    if (q !== search.trim()) setSearch(q);
  }

  function update(changes: Record<string, string>) {
    const next = new URLSearchParams(params);
    for (const [key, value] of Object.entries(changes)) {
      if (value) next.set(key, value);
      else next.delete(key);
    }
    if (!("page" in changes)) next.delete("page");
    setParams(next, { replace: true });
  }

  // Recherche anti-rebond : l'URL (donc la requête) n'est mise à jour que 300 ms après la frappe.
  useEffect(() => {
    const trimmed = search.trim().slice(0, 100);
    if (trimmed === q) return;
    const timer = setTimeout(() => {
      const next = new URLSearchParams(params);
      if (trimmed) next.set("q", trimmed);
      else next.delete("q");
      next.delete("page");
      setParams(next, { replace: true });
    }, DEBOUNCE_MS);
    return () => clearTimeout(timer);
  }, [search, q, params, setParams]);

  const query: MissionParams = {
    q: q || undefined,
    statut: (statut as StatutMission) || undefined,
    type: (type as TypeMission) || undefined,
    annee: annee ? Number(annee) : undefined,
    ordering: ordering || undefined,
    page,
    page_size: PAGE_SIZE,
  };
  const { data, isLoading, isError, refetch } = useMissions(query);

  const filtered = q !== "" || statut !== "" || type !== "" || annee !== "";
  const createButton = isRai && (
    <Button asChild>
      <Link to="nouvelle">
        <Plus aria-hidden />
        {m.createMission}
      </Link>
    </Button>
  );

  const empty = filtered ? (
    <EmptyState title={m.emptyFiltered} illustration={false} />
  ) : isRai ? (
    <EmptyState title={m.emptyRai}>{createButton}</EmptyState>
  ) : is("AUDITEUR") ? (
    <EmptyState title={m.emptyAuditeur} />
  ) : (
    <EmptyState title={m.emptyAudite} />
  );

  const year = currentYear();
  const years = Array.from({ length: 8 }, (_, i) => year + 2 - i);

  return (
    <div className="grid gap-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-2xl font-semibold tracking-[-0.012em]">{fr.missions.title}</h1>
        <div className="print:hidden">{createButton}</div>
      </div>

      <form
        role="search"
        className="flex flex-wrap items-end gap-3 print:hidden"
        onSubmit={(e) => e.preventDefault()}
      >
        <div className="grid gap-1.5">
          <Label htmlFor="mission-q">{m.searchLabel}</Label>
          <Input
            id="mission-q"
            type="search"
            value={search}
            maxLength={100}
            placeholder={m.searchPlaceholder}
            onChange={(e) => setSearch(e.target.value)}
            className="w-64"
          />
        </div>
        <div className="grid gap-1.5">
          <Label htmlFor="mission-statut">{fr.missions.filterStatus}</Label>
          <NativeSelect
            id="mission-statut"
            value={statut}
            onChange={(e) => update({ statut: e.target.value })}
          >
            <option value="">{fr.missions.allStatuses}</option>
            {STATUSES.map((s) => (
              <option key={s} value={s}>
                {STATUT_MISSION_LABELS[s]}
              </option>
            ))}
          </NativeSelect>
        </div>
        <div className="grid gap-1.5">
          <Label htmlFor="mission-type">{fr.missions.filterType}</Label>
          <NativeSelect
            id="mission-type"
            value={type}
            onChange={(e) => update({ type: e.target.value })}
          >
            <option value="">{fr.missions.allTypes}</option>
            {TYPES.map((t) => (
              <option key={t} value={t}>
                {TYPE_MISSION_LABELS[t]}
              </option>
            ))}
          </NativeSelect>
        </div>
        <div className="grid gap-1.5">
          <Label htmlFor="mission-annee">{m.filterYear}</Label>
          <NativeSelect
            id="mission-annee"
            value={annee}
            onChange={(e) => update({ annee: e.target.value })}
          >
            <option value="">{m.allYears}</option>
            {years.map((y) => (
              <option key={y} value={y}>
                {y}
              </option>
            ))}
          </NativeSelect>
        </div>
      </form>

      {isError ? (
        <div role="alert" className={ALERT_CLASS}>
          <p>{fr.missions.loadError}</p>
          <Button
            type="button"
            variant="outline"
            size="sm"
            className="mt-2"
            onClick={() => void refetch()}
          >
            {fr.common.retry}
          </Button>
        </div>
      ) : (
        <DataTable
          caption={m.listCaption}
          columns={COLUMNS}
          data={data?.results ?? []}
          total={data?.count ?? 0}
          page={page}
          pageSize={PAGE_SIZE}
          onPageChange={(p) => update({ page: String(p) })}
          ordering={ordering}
          onOrderingChange={(o) => update({ ordering: o })}
          isLoading={isLoading}
          empty={empty}
        />
      )}
    </div>
  );
}
