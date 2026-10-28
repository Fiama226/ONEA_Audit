import { Lock } from "lucide-react";
import { fr } from "@/i18n/fr";
import { formatDate } from "@/lib/dates";
import type { CartographieVersion } from "../types";

/** Bandeau d'une version validée (figée, lecture seule). */
export function FrozenBanner({ version }: { version: CartographieVersion }) {
  const c = fr.refCartographie;
  const date = version.validee_le ? ` ${formatDate(version.validee_le)}` : "";
  const by = version.validee_par ? ` ${c.frozenBy} ${version.validee_par.nom_complet}` : "";
  return (
    <p
      role="status"
      className="flex items-center gap-2 rounded-md border border-border bg-surface-subtle px-4 py-3 text-sm"
    >
      <Lock className="size-4 shrink-0" aria-hidden />
      <span>{`${c.frozenOn}${date}${by} : ${c.frozenSuffix}`}</span>
    </p>
  );
}
