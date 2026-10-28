import { useQuery } from "@tanstack/react-query";
import { fetchAllPages, referentielKeys, type DirectionParams, type ProcessParams } from "./api";
import type { Direction, Processus } from "./types";

type Unpaged<P> = Omit<P, "page" | "page_size">;

/** Toutes les directions et départements (sans pagination visible). */
export function useAllDirections(params: Unpaged<DirectionParams> = {}) {
  return useQuery({
    queryKey: [...referentielKeys.directions(), "all", params],
    queryFn: () => fetchAllPages<Direction>("directions", params),
  });
}

/** Tous les processus (sans pagination visible). */
export function useAllProcesses(params: Unpaged<ProcessParams> = {}) {
  return useQuery({
    queryKey: [...referentielKeys.processes(), "all", params],
    queryFn: () => fetchAllPages<Processus>("processes", params),
  });
}

export { fetchAllPages, type AllPages } from "./api";
