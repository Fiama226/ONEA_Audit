import { useState } from "react";
import { NativeSelect } from "@/components/form/NativeSelect";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { fr } from "@/i18n/fr";
import { formatDateTime } from "@/lib/dates";
import { useInterviewAction } from "../api";
import { STATUT_ENTRETIEN_LABELS } from "../labels";
import type { Entretien, Mission, StatutEntretien } from "../types";
import { ConfirmActionDialog } from "./ConfirmActionDialog";
import { InterviewFormDialog } from "./InterviewFormDialog";
import { MotifDialog } from "./MotifDialog";

const t = fr.missionTravaux;

type Props = {
  mission: Mission;
  interviews: Entretien[];
  /** Affiche le filtre par statut. */
  filterable?: boolean;
  /** Nom accessible du tableau. */
  label: string;
};

function names(e: Entretien, key: "auditeurs_detail" | "interlocuteurs_detail"): string {
  const list = e[key].map((u) => u.nom_complet);
  if (key === "interlocuteurs_detail" && e.autres_interlocuteurs) {
    list.push(...e.autres_interlocuteurs.split("\n").filter((l) => l.trim() !== ""));
  }
  return list.join(", ");
}

/** Tableau des entretiens triés par date. Les actions dépendent de `mes_droits` du serveur. */
export function InterviewTable({ mission, interviews, filterable = false, label }: Props) {
  const [status, setStatus] = useState<"" | StatutEntretien>("");
  const [editing, setEditing] = useState<Entretien | null>(null);
  const [doing, setDoing] = useState<Entretien | null>(null);
  const [cancelling, setCancelling] = useState<Entretien | null>(null);
  const action = useInterviewAction();

  const rows = interviews
    .filter((e) => status === "" || e.statut === status)
    .sort((a, b) => a.date_prevue.localeCompare(b.date_prevue));
  const canWrite = mission.mes_droits.contribuer;

  return (
    <div className="grid gap-3">
      {filterable && (
        <div className="grid max-w-xs gap-1.5 print:hidden">
          <Label htmlFor="interview-status-filter">{t.filterStatus}</Label>
          <NativeSelect
            id="interview-status-filter"
            value={status}
            onChange={(e) => setStatus(e.target.value as "" | StatutEntretien)}
          >
            <option value="">{t.allStatuses}</option>
            {(Object.keys(STATUT_ENTRETIEN_LABELS) as StatutEntretien[]).map((s) => (
              <option key={s} value={s}>
                {STATUT_ENTRETIEN_LABELS[s]}
              </option>
            ))}
          </NativeSelect>
        </div>
      )}
      <div className="overflow-hidden rounded-md border border-border">
        <Table aria-label={label}>
          <TableHeader>
            <TableRow>
              <TableHead>{t.colDate}</TableHead>
              <TableHead>{t.colObject}</TableHead>
              <TableHead>{t.colStep}</TableHead>
              <TableHead>{t.colInterlocutors}</TableHead>
              <TableHead>{t.colAuditors}</TableHead>
              <TableHead>{t.colStatus}</TableHead>
              {canWrite && (
                <TableHead className="print:hidden">
                  <span className="sr-only">{fr.common.actions}</span>
                </TableHead>
              )}
            </TableRow>
          </TableHeader>
          <TableBody>
            {rows.length === 0 && (
              <TableRow>
                <TableCell colSpan={canWrite ? 7 : 6} className="text-text-muted">
                  {t.noInterview}
                </TableCell>
              </TableRow>
            )}
            {rows.map((e) => {
              const writable = canWrite && !e.etape_close;
              return (
                <TableRow key={e.id}>
                  <TableCell className="whitespace-nowrap">
                    {formatDateTime(e.date_prevue)}
                  </TableCell>
                  <TableCell className="whitespace-normal">{e.objet}</TableCell>
                  <TableCell>{e.etape_romain ?? "—"}</TableCell>
                  <TableCell className="whitespace-normal">
                    {names(e, "interlocuteurs_detail") || "—"}
                  </TableCell>
                  <TableCell className="whitespace-normal">
                    {names(e, "auditeurs_detail") || "—"}
                  </TableCell>
                  <TableCell>{STATUT_ENTRETIEN_LABELS[e.statut]}</TableCell>
                  {canWrite && (
                    <TableCell className="print:hidden">
                      {writable && e.statut !== "ANNULE" && (
                        <div className="flex flex-wrap gap-2">
                          <Button
                            type="button"
                            variant="outline"
                            size="sm"
                            aria-label={`${t.enterMinutes} : ${e.objet}`}
                            onClick={() => setEditing(e)}
                          >
                            {t.enterMinutes}
                          </Button>
                          {e.statut === "PLANIFIE" && (
                            <>
                              <Button
                                type="button"
                                variant="outline"
                                size="sm"
                                aria-label={`${t.markDone} : ${e.objet}`}
                                onClick={() => setDoing(e)}
                              >
                                {t.markDone}
                              </Button>
                              <Button
                                type="button"
                                variant="outline"
                                size="sm"
                                aria-label={`${t.cancelInterview} : ${e.objet}`}
                                onClick={() => setCancelling(e)}
                              >
                                {t.cancelInterview}
                              </Button>
                            </>
                          )}
                        </div>
                      )}
                    </TableCell>
                  )}
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
      </div>

      {canWrite && editing && (
        <InterviewFormDialog
          open
          onOpenChange={(open) => !open && setEditing(null)}
          mission={mission}
          interview={editing}
        />
      )}
      {canWrite && (
        <ConfirmActionDialog
          open={doing !== null}
          onOpenChange={(open) => !open && setDoing(null)}
          title={t.markDoneTitle}
          text={t.markDoneText}
          confirmLabel={t.markDone}
          onConfirm={() =>
            doing ? action.mutateAsync({ id: doing.id, action: "mark-done" }) : Promise.resolve()
          }
        />
      )}
      {canWrite && (
        <MotifDialog
          open={cancelling !== null}
          onOpenChange={(open) => !open && setCancelling(null)}
          title={t.cancelInterviewTitle}
          description={t.cancelInterviewText}
          confirmLabel={t.cancelInterview}
          onSubmit={(motif) =>
            cancelling
              ? action.mutateAsync({ id: cancelling.id, action: "cancel", motif })
              : Promise.resolve()
          }
        />
      )}
    </div>
  );
}
