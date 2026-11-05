import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useId, useState } from "react";
import { apiFetch } from "@/api/client";
import { isApiError } from "@/api/errors";
import { toQuery } from "@/api/query";
import type { components } from "@/api/schema";
import { useAuth } from "@/auth/useAuth";
import { ALERT_CLASS } from "@/components/form/FormField";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { useMission } from "@/features/missions/api";
import { fr } from "@/i18n/fr";
import { formatDateTime } from "@/lib/dates";

type Accord = components["schemas"]["AccordResultats"];
type Position = "ACCORD" | "DESACCORD";

const t = fr.accordResultats;
const key = (missionId: string) => ["accomplissement", "accords-resultats", missionId] as const;

/**
 * Étape XIII « avec les audités » : l'audité responsable de son entité donne sa position sur les
 * résultats des tests (accord, ou désaccord motivé). Exigée pour clore XIII selon la règle de
 * gouvernance « réponse de l'audité ».
 */
export function ResultsAgreementCard({ missionId }: { missionId: string }) {
  const id = useId();
  const client = useQueryClient();
  const { me } = useAuth();
  const mission = useMission(missionId);
  const accords = useQuery({
    queryKey: key(missionId),
    queryFn: () =>
      apiFetch<Accord[]>(`/api/v1/test-results-agreements/${toQuery({ mission: missionId })}`),
  });
  const give = useMutation({
    mutationFn: (body: { entite: string; position: Position; commentaire: string }) =>
      apiFetch<Accord>("/api/v1/test-results-agreements/", {
        method: "POST",
        json: { mission: missionId, ...body },
      }),
    onSuccess: () => client.invalidateQueries({ queryKey: key(missionId) }),
  });
  const [position, setPosition] = useState<Position>("ACCORD");
  const [commentaire, setCommentaire] = useState("");
  const [error, setError] = useState<string | null>(null);

  const data = mission.data;
  const mine = data?.equipe.find((a) => a.utilisateur === me?.id);
  const entite = data?.entites_detail.find((e) => e.code === me?.direction_code);
  const history = accords.data ?? [];
  const isHead = Boolean(mine?.responsable_entite && entite);
  if (!data || (!isHead && history.length === 0)) return null;
  if (data.statut !== "EN_ACCOMPLISSEMENT" && history.length === 0) return null;

  async function submit() {
    if (!entite) return;
    setError(null);
    if (position === "DESACCORD" && !commentaire.trim()) {
      setError(t.commentRequired);
      return;
    }
    try {
      await give.mutateAsync({ entite: entite.id, position, commentaire: commentaire.trim() });
      setCommentaire("");
    } catch (e) {
      setError(isApiError(e) ? e.detail : fr.errors.generic);
    }
  }

  return (
    <section
      aria-labelledby={`${id}-title`}
      className="grid gap-3 rounded-lg border border-border bg-surface p-4 text-sm"
    >
      <h3 id={`${id}-title`} className="text-base font-semibold">
        {t.title}
      </h3>
      <p className="max-w-[75ch] text-text-muted">{t.help}</p>
      {history.length > 0 && (
        <ul className="m-0 grid list-none gap-1 p-0">
          {history.map((a) => (
            <li key={a.id}>
              {t.line(
                a.entite_libelle,
                a.position === "ACCORD" ? t.agree : t.disagree,
                formatDateTime(a.created_at),
              )}
              {a.commentaire && <span className="block text-text-muted">{a.commentaire}</span>}
            </li>
          ))}
        </ul>
      )}
      {isHead && data.statut === "EN_ACCOMPLISSEMENT" && (
        <form
          className="grid gap-3"
          noValidate
          onSubmit={(e) => {
            e.preventDefault();
            void submit();
          }}
        >
          <fieldset className="flex flex-wrap gap-4">
            <legend className="mb-1 font-medium">{t.positionLegend(entite?.libelle ?? "")}</legend>
            {(["ACCORD", "DESACCORD"] as const).map((p) => (
              <label key={p} className="flex items-center gap-2">
                <input
                  type="radio"
                  name={`${id}-position`}
                  value={p}
                  checked={position === p}
                  onChange={() => setPosition(p)}
                />
                {p === "ACCORD" ? t.agree : t.disagree}
              </label>
            ))}
          </fieldset>
          <div className="grid gap-1.5">
            <Label htmlFor={`${id}-comment`}>{t.comment}</Label>
            <Textarea
              id={`${id}-comment`}
              rows={3}
              value={commentaire}
              onChange={(e) => setCommentaire(e.target.value)}
            />
          </div>
          {error && (
            <p role="alert" className={ALERT_CLASS}>
              {error}
            </p>
          )}
          <div>
            <Button type="submit" size="sm" disabled={give.isPending}>
              {t.submit}
            </Button>
          </div>
        </form>
      )}
    </section>
  );
}
