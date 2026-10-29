import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { fetchAllPages } from "@/api/allPages";
import { isApiError } from "@/api/errors";
import { ListIncompleteAlert } from "@/components/ListIncompleteAlert";
import { ALERT_CLASS } from "@/components/form/FormField";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import type { Risque } from "@/features/referentiel/types";
import { fr } from "@/i18n/fr";
import { useSaveMissionRisk } from "../api";
import { missionKeys } from "../keys";
import type { Mission } from "../types";

const m = fr.missionEtapes;

type Props = {
  mission: Mission;
  /** Identifiants des risques de cartographie déjà retenus par la mission. */
  selectedSources: ReadonlySet<string>;
  open: boolean;
  onOpenChange: (open: boolean) => void;
};

/** Tous les risques de la cartographie de la mission, pour chacun de ses processus. */
function useCandidateRisks(mission: Mission, enabled: boolean) {
  const version = mission.cartographie?.id;
  const processIds = mission.processus_detail.map((p) => p.id);
  return useQuery({
    queryKey: [...missionKeys.all, "risk-candidates", version, processIds],
    enabled: enabled && version !== undefined,
    queryFn: async () => {
      const parts = await Promise.all(
        processIds.map((processus) => fetchAllPages<Risque>("risks", { version, processus })),
      );
      const seen = new Set<string>();
      const results = parts
        .flatMap((p) => p.results)
        .filter((r) => processIds.includes(r.processus) && !seen.has(r.id) && seen.add(r.id));
      return { results, count: parts.reduce((sum, p) => sum + p.count, 0) };
    },
  });
}

export function RiskSelectDialog({ mission, selectedSources, open, onOpenChange }: Props) {
  const candidates = useCandidateRisks(mission, open);
  const save = useSaveMissionRisk();
  const [chosen, setChosen] = useState<ReadonlySet<string>>(new Set());
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);
  const results = candidates.data?.results ?? [];

  function close(next: boolean) {
    if (pending) return;
    if (!next) {
      setChosen(new Set());
      setError(null);
    }
    onOpenChange(next);
  }

  function toggle(id: string, on: boolean) {
    const next = new Set(chosen);
    if (on) next.add(id);
    else next.delete(id);
    setChosen(next);
  }

  async function submit() {
    setPending(true);
    setError(null);
    try {
      for (const risque_source of chosen) {
        await save.mutateAsync({ data: { mission: mission.id, risque_source } });
        // Déjà enregistré : une nouvelle tentative après un échec partiel ne le renvoie pas.
        setChosen((prev) => {
          const next = new Set(prev);
          next.delete(risque_source);
          return next;
        });
      }
      setChosen(new Set());
      setPending(false);
      onOpenChange(false);
    } catch (e) {
      setError(isApiError(e) ? e.detail : fr.errors.generic);
      setPending(false);
    }
  }

  const title = mission.cartographie
    ? m.selectRisks.replace("{annee}", String(mission.cartographie.annee))
    : m.selectRisksNoMap;

  return (
    <Dialog open={open} onOpenChange={close}>
      <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-2xl">
        <DialogHeader>
          <DialogTitle>{title}</DialogTitle>
          <DialogDescription>{m.selectDescription}</DialogDescription>
        </DialogHeader>
        {candidates.isError ? (
          <p role="alert" className={ALERT_CLASS}>
            {m.selectLoadError}
          </p>
        ) : candidates.isLoading ? (
          <p role="status" className="text-sm text-text-muted">
            {fr.common.loading}
          </p>
        ) : (
          <>
            <ListIncompleteAlert count={candidates.data?.count ?? 0} loaded={results.length} />
            {results.length === 0 ? (
              <p className="text-sm text-text-muted">{m.selectEmpty}</p>
            ) : (
              <ul className="grid max-h-80 gap-1 overflow-y-auto" aria-label={title}>
                {results.map((r) => {
                  const already = selectedSources.has(r.id);
                  const boxId = `risk-pick-${r.id}`;
                  return (
                    <li key={r.id} className="flex items-start gap-2 py-1">
                      <Checkbox
                        id={boxId}
                        checked={already || chosen.has(r.id)}
                        disabled={already}
                        onCheckedChange={(v) => toggle(r.id, v === true)}
                      />
                      <Label htmlFor={boxId} className="grid gap-0.5 font-normal">
                        <span>
                          <span className="font-medium">{r.code}</span> · {r.libelle}
                        </span>{" "}
                        <span className="text-xs text-text-muted">
                          {r.processus_code} · {r.probabilite}×{r.impact} = {r.score}
                          {already && ` · ${m.selectAlready}`}
                        </span>
                      </Label>
                    </li>
                  );
                })}
              </ul>
            )}
          </>
        )}
        {error && (
          <p role="alert" className={ALERT_CLASS}>
            {error}
          </p>
        )}
        <DialogFooter className="items-center">
          <span role="status" className="mr-auto text-sm text-text-muted">
            {m.selectCount.replace("{count}", String(chosen.size))}
          </span>
          <Button type="button" variant="outline" disabled={pending} onClick={() => close(false)}>
            {fr.common.cancel}
          </Button>
          <Button
            type="button"
            disabled={pending || chosen.size === 0}
            onClick={() => void submit()}
          >
            {m.selectSubmit}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
