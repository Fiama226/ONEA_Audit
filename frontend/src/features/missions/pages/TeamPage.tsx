import { useState } from "react";
import { useParams } from "react-router-dom";
import { useAuth } from "@/auth/useAuth";
import { DataTable, type DataTableColumn } from "@/components/DataTable";
import { ALERT_CLASS } from "@/components/form/FormField";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { fr } from "@/i18n/fr";
import { formatDate } from "@/lib/dates";
import { useMission, useSetEntityManager, useUnassign } from "../api";
import { ArbitrateDialog } from "../components/ArbitrateDialog";
import { AssignDialog } from "../components/AssignDialog";
import { ConfirmActionDialog } from "../components/ConfirmActionDialog";
import { DeclarationDialog } from "../components/DeclarationDialog";
import { ROLE_MISSION_LABELS } from "../labels";
import type { Affectation, Mission } from "../types";

const m = fr.missionPilotage;

function declarationText(a: Affectation): string {
  const d = a.declaration;
  if (!d) return m.declNone;
  if (d.statut === "CONFIRMEE") {
    return m.declConfirmed.replace("{date}", d.confirmee_le ? formatDate(d.confirmee_le) : "");
  }
  if (d.statut === "CONFLIT_DECLARE") return d.levee ? m.declArbitrated : m.declSituation;
  return m.declPending;
}

type Dialog =
  | { kind: "assign" }
  | { kind: "replace" }
  | { kind: "declare" }
  | { kind: "arbitrate"; affectation: string }
  | { kind: "unassign"; affectation: Affectation }
  | { kind: "entity-manager"; affectation: Affectation };

export function TeamPage() {
  const { id } = useParams();
  const { me } = useAuth();
  const mission = useMission(id);
  const unassign = useUnassign();
  const setEntityManager = useSetEntityManager();
  const [dialog, setDialog] = useState<Dialog | null>(null);

  if (mission.isError) {
    return (
      <p role="alert" className={ALERT_CLASS}>
        {fr.missions.loadError}
      </p>
    );
  }
  if (!mission.data) {
    return (
      <p role="status" className="text-sm text-text-muted">
        {fr.common.loading}
      </p>
    );
  }
  const data: Mission = mission.data;
  const canAssign = data.mes_droits.affecter;

  const columns: DataTableColumn<Affectation>[] = [
    {
      id: "nom",
      header: m.colName,
      enableSorting: false,
      cell: ({ row }) => row.original.utilisateur_detail.nom_complet,
    },
    {
      id: "fonction",
      header: m.colFunction,
      enableSorting: false,
      cell: ({ row }) => row.original.utilisateur_detail.fonction || "-",
    },
    {
      id: "role",
      header: m.colRole,
      enableSorting: false,
      cell: ({ row }) => (
        <span className="flex flex-wrap items-center gap-2">
          {ROLE_MISSION_LABELS[row.original.role_mission]}
          {row.original.responsable_entite && <Badge variant="secondary">{m.entityManager}</Badge>}
        </span>
      ),
    },
    {
      id: "declaration",
      header: m.colDeclaration,
      enableSorting: false,
      cell: ({ row }) => declarationText(row.original),
    },
    {
      id: "actions",
      header: fr.refStructure.actionsColumn,
      enableSorting: false,
      cell: ({ row }) => {
        const a = row.original;
        const mine = me?.id === a.utilisateur;
        const name = a.utilisateur_detail.nom_complet;
        return (
          <div className="flex flex-wrap gap-2 print:hidden">
            {mine && data.mes_droits.confirmer_ma_declaration && (
              <Button type="button" size="sm" onClick={() => setDialog({ kind: "declare" })}>
                {m.confirmMyDeclaration}
              </Button>
            )}
            {canAssign && a.declaration?.statut === "CONFLIT_DECLARE" && !a.declaration.levee && (
              <Button
                type="button"
                size="sm"
                variant="outline"
                aria-label={`${m.arbitrate} : ${name}`}
                onClick={() => setDialog({ kind: "arbitrate", affectation: a.id })}
              >
                {m.arbitrate}
              </Button>
            )}
            {canAssign && a.role_mission === "CHEF_MISSION" && (
              <Button
                type="button"
                size="sm"
                variant="outline"
                onClick={() => setDialog({ kind: "replace" })}
              >
                {m.replaceChief}
              </Button>
            )}
            {canAssign && a.role_mission === "AUDITE" && (
              <Button
                type="button"
                size="sm"
                variant="outline"
                aria-label={`${a.responsable_entite ? m.entityManagerUnset : m.entityManagerSet} : ${name}`}
                onClick={() => setDialog({ kind: "entity-manager", affectation: a })}
              >
                {a.responsable_entite ? m.entityManagerUnset : m.entityManagerSet}
              </Button>
            )}
            {canAssign && a.role_mission !== "CHEF_MISSION" && (
              <Button
                type="button"
                size="sm"
                variant="outline"
                aria-label={`${m.unassign} : ${name}`}
                onClick={() => setDialog({ kind: "unassign", affectation: a })}
              >
                {m.unassign}
              </Button>
            )}
          </div>
        );
      },
    },
  ];
  // Colonne d'actions inutile quand aucune action n'est possible (audité, auditeur non concerné).
  const visibleColumns = columns.filter((c) =>
    c.id === "declaration"
      ? data.mes_droits.voir_travaux
      : c.id !== "actions" || canAssign || data.mes_droits.confirmer_ma_declaration,
  );

  return (
    <section aria-labelledby="team-title" className="grid gap-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 id="team-title" className="text-lg font-semibold">
          {m.teamTitle}
        </h2>
        {canAssign && (
          <Button
            type="button"
            className="print:hidden"
            onClick={() => setDialog({ kind: "assign" })}
          >
            {m.assign}
          </Button>
        )}
      </div>
      <DataTable
        caption={m.teamCaption}
        columns={visibleColumns}
        data={data.equipe}
        total={data.equipe.length}
        page={1}
        pageSize={Math.max(1, data.equipe.length)}
        onPageChange={() => undefined}
        isLoading={false}
        empty={<p className="text-sm text-text-muted">{m.teamEmpty}</p>}
      />

      {dialog?.kind === "assign" && (
        <AssignDialog mission={data} mode="assign" onClose={() => setDialog(null)} />
      )}
      {dialog?.kind === "replace" && (
        <AssignDialog mission={data} mode="replace-chief" onClose={() => setDialog(null)} />
      )}
      {dialog?.kind === "declare" && (
        <DeclarationDialog missionId={data.id} onClose={() => setDialog(null)} />
      )}
      {dialog?.kind === "arbitrate" && (
        <ArbitrateDialog
          missionId={data.id}
          affectationId={dialog.affectation}
          onClose={() => setDialog(null)}
        />
      )}
      {dialog?.kind === "entity-manager" && (
        <ConfirmActionDialog
          open
          onOpenChange={(open) => !open && setDialog(null)}
          title={
            dialog.affectation.responsable_entite
              ? m.entityManagerUnsetTitle
              : m.entityManagerSetTitle
          }
          text={
            dialog.affectation.responsable_entite
              ? m.entityManagerUnsetText
              : m.entityManagerSetText
          }
          confirmLabel={
            dialog.affectation.responsable_entite ? m.entityManagerUnset : m.entityManagerSet
          }
          requireCheck={false}
          onConfirm={() =>
            setEntityManager.mutateAsync({
              id: dialog.affectation.id,
              responsable: !dialog.affectation.responsable_entite,
            })
          }
        />
      )}
      {dialog?.kind === "unassign" && (
        <ConfirmActionDialog
          open
          onOpenChange={(open) => !open && setDialog(null)}
          title={m.unassignTitle}
          text={m.unassignText}
          confirmLabel={m.unassign}
          onConfirm={() => unassign.mutateAsync({ id: dialog.affectation.id, missionId: data.id })}
        />
      )}
    </section>
  );
}
