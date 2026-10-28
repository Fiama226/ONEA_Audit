import { fr } from "@/i18n/fr";

/** `creating` : création sous `:id/nouvelle-ligne` ; sinon modification ou lecture de `lignes/:lineId`. */
export function AuditPlanLineFormPage(props: { creating?: boolean }) {
  void props;
  return <h1 className="text-2xl font-semibold">{fr.programmation.title}</h1>;
}
