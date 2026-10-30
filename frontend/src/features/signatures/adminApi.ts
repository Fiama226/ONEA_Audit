import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "@/api/client";
import type { components } from "@/api/schema";

export type ParametreSignature = components["schemas"]["ParametreSignature"];
export type ModeSignature = components["schemas"]["ModeSignatureParametreEnum"];

const KEY = ["signature-settings"] as const;
const BASE = "/api/v1/signature-settings/";

export function useSignatureSettings() {
  return useQuery({
    queryKey: KEY,
    queryFn: () => apiFetch<ParametreSignature[]>(BASE),
  });
}

export function useUpdateSignatureSetting() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({ typeDocument, mode }: { typeDocument: string; mode: ModeSignature }) =>
      apiFetch<ParametreSignature>(`${BASE}${encodeURIComponent(typeDocument)}/`, {
        method: "PATCH",
        json: { mode },
      }),
    onSuccess: () => client.invalidateQueries({ queryKey: KEY }),
  });
}
