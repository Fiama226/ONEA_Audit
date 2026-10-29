import { useState } from "react";
import { Link } from "react-router-dom";
import { useAuth } from "@/auth/useAuth";
import { Button } from "@/components/ui/button";
import { fr } from "@/i18n/fr";
import { formatDate } from "@/lib/dates";
import { useMissionTransition } from "../api";
import { ConfirmActionDialog } from "../components/ConfirmActionDialog";
import { shortHash } from "../components/DeclarationDialog";
import { ROLE_MISSION_LABELS } from "../labels";
import type { Etape, Mission } from "../types";

const m = fr.missionPilotage;

function Recap({ term, children }: { term: string; children: string }) {
  return (
    <div>
      <dt className="text-sm text-text-muted">{term}</dt>
      <dd className="whitespace-pre-line text-sm">{children || m.stepINone}</dd>
    </div>
  );
}

/** Étape I : rappel de la mission et émission de l'ordre de mission (confirmation horodatée). */
export function StepIZone({ mission }: { mission: Mission; step: Etape }) {
  const { me } = useAuth();
  const transition = useMissionTransition();
  const [confirming, setConfirming] = useState(false);

  const { debut, fin } = {
    debut: mission.date_debut_prevue,
    fin: mission.date_fin_prevue,
  };
  const name = me ? `${me.first_name} ${me.last_name}`.trim() || me.username : "";
  const order = mission.ordre_mission;
  const issued = order !== null && !mission.mes_droits.emettre_ordre;

  return (
    <section aria-labelledby="step-one-recap" className="grid gap-6">
      <div className="grid gap-3">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <h3 id="step-one-recap" className="text-lg font-semibold">
            {m.stepIRecap}
          </h3>
          {mission.mes_droits.modifier && (
            <Button asChild variant="outline" size="sm" className="print:hidden">
              <Link to={`/missions/${mission.id}/modifier`}>{m.stepIEdit}</Link>
            </Button>
          )}
        </div>
        <dl className="grid gap-3">
          <Recap term={m.stepIObjectives}>{mission.objectifs ?? ""}</Recap>
          <Recap term={m.stepIScope}>{mission.perimetre ?? ""}</Recap>
          <Recap term={m.stepITeam}>
            {mission.equipe
              .map(
                (a) =>
                  `${a.utilisateur_detail.nom_complet} (${ROLE_MISSION_LABELS[a.role_mission]})`,
              )
              .join(", ")}
          </Recap>
          <Recap term={m.stepIDates}>
            {debut && fin ? `${formatDate(debut)} - ${formatDate(fin)}` : fr.missions.noDates}
          </Recap>
        </dl>
      </div>

      {issued && order && (
        <div
          role="status"
          className="rounded-md border border-border bg-surface-subtle p-4 text-sm"
        >
          <p className="font-medium">
            {m.orderIssued
              .replace("{date}", formatDate(order.confirme_le))
              .replace("{name}", order.signataire.nom_complet)}
          </p>
          <p title={order.empreinte}>{m.orderHash.replace("{hash}", shortHash(order.empreinte))}</p>
          <p className="text-text-muted">{m.orderWordLater}</p>
        </div>
      )}
      {!issued && !mission.mes_droits.emettre_ordre && (
        <p className="text-sm text-text-muted">{m.issueOrderPending}</p>
      )}

      {mission.mes_droits.emettre_ordre && (
        <div className="print:hidden">
          <Button type="button" onClick={() => setConfirming(true)}>
            {m.issueOrder}
          </Button>
          <ConfirmActionDialog
            open={confirming}
            onOpenChange={setConfirming}
            title={m.issueOrderTitle}
            text={m.issueOrderText
              .replace("{name}", name)
              .replace("{reference}", mission.reference)
              .replace("{title}", mission.titre)}
            confirmLabel={m.issueOrderConfirm}
            onConfirm={() => transition.mutateAsync({ id: mission.id, action: "issue-order" })}
          />
        </div>
      )}
    </section>
  );
}
