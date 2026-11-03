import { useState } from "react";
import { ALERT_CLASS } from "@/components/form/FormField";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ConfirmActionDialog } from "@/features/missions/components/ConfirmActionDialog";
import { fr } from "@/i18n/fr";
import { formatDateTime } from "@/lib/dates";
import { useReportAction, useReportSignature } from "../api";
import type { Rapport } from "../types";

const t = fr.rapportFinal;

/**
 * Signature électronique PAdES du rapport final : état vérifié par le serveur (signataire,
 * date, validité) et, pour le RAI seul, action « Signer ». N'apparaît que si le mode de
 * signature exige la signature électronique ou si le rapport est déjà signé.
 */
export function SignaturePanel({ rapport }: { rapport: Rapport }) {
  const requise = rapport.signature_electronique_requise;
  const signature = useReportSignature(rapport.id, requise || rapport.statut === "DIFFUSE");
  const action = useReportAction();
  const [open, setOpen] = useState(false);
  const [lieu, setLieu] = useState("");
  const peutSigner = rapport.statut === "VALIDE" && rapport.actions_possibles.includes("DIFFUSER");

  if (!requise && !(signature.data?.signee ?? false)) return null;
  const etat = signature.data;

  return (
    <section aria-labelledby="signature-title" className="grid gap-2">
      <h3 id="signature-title" className="text-base font-semibold">
        {t.signatureTitle}
      </h3>
      {signature.isPending && (
        <p role="status" className="text-sm text-text-muted">
          {fr.common.loading}
        </p>
      )}
      {signature.isError && (
        <p role="alert" className={ALERT_CLASS}>
          {t.signatureLoadError}
        </p>
      )}
      {etat && !etat.signee && (
        <p role="status" className="text-sm text-text-muted">
          {t.signatureNone}
        </p>
      )}
      {etat?.signee && (
        <div className="grid gap-1 text-sm">
          <p>
            <span className="font-medium">
              {etat.valide ? t.signatureValid : t.signatureInvalid}
            </span>
            {!etat.valide && etat.motif !== "" && <span> : {etat.motif}</span>}
          </p>
          <p>
            {t.signatureBy
              .replace("{nom}", etat.signe_par)
              .replace("{date}", etat.signe_le ? formatDateTime(etat.signe_le) : "")
              .replace("{sujet}", etat.signataire)}
          </p>
          {etat.horodatage_tsa && <p>{t.signatureTsa}</p>}
        </div>
      )}
      {etat && !etat.signee && peutSigner && (
        <>
          <label className="grid gap-1.5 text-sm font-medium" htmlFor="signature-lieu">
            {t.signaturePlace}
            <Input id="signature-lieu" value={lieu} onChange={(e) => setLieu(e.target.value)} />
          </label>
          <div>
            <Button type="button" onClick={() => setOpen(true)}>
              {t.signatureSign}
            </Button>
          </div>
          <ConfirmActionDialog
            open={open}
            onOpenChange={setOpen}
            title={t.signatureConfirmTitle}
            text={t.signatureConfirmText}
            confirmLabel={t.signatureConfirm}
            onConfirm={() =>
              action.mutateAsync({
                id: rapport.id,
                missionId: rapport.mission,
                action: "sign",
                payload: { lieu },
              })
            }
          />
        </>
      )}
    </section>
  );
}
