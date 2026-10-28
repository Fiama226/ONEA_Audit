import type { components } from "@/api/schema";

type S = components["schemas"];

export type Direction = S["Direction"];
export type DirectionInput = S["DirectionRequest"];
export type Processus = S["Processus"];
export type ProcessusInput = S["ProcessusRequest"];
export type ObjetAuditable = S["ObjetAuditable"];
export type ObjetAuditableInput = S["ObjetAuditableRequest"];
export type DomaineArbre = S["DomaineArbre"];
export type CartographieVersion = S["CartographieVersion"];
export type CartographieVersionInput = S["CartographieVersionRequest"];
export type Risque = S["Risque"];
export type RisqueInput = S["RisqueRequest"];
export type Matrice = S["Matrice"];
export type CelluleMatrice = S["CelluleMatrice"];
export type Comparaison = S["Comparaison"];

export type FamilleProcessus = S["FamilleProcessusEnum"];
export type TypeEntite = S["TypeEntiteEnum"];
export type NatureObjet = S["NatureObjetEnum"];
export type NiveauRisque = S["NiveauRisqueEnum"];
export type ReponseRisque = S["ReponseRisqueEnum"];
export type PrioriteRisque = S["PrioriteRisqueEnum"];
export type StatutCartographie = S["StatutCartographieEnum"];

export type Page<T> = {
  count: number;
  next?: string | null;
  previous?: string | null;
  results: T[];
};

/** Paramètres de liste communs (pagination, tri serveur). */
export type ListParams = { page?: number; page_size?: number; ordering?: string; q?: string };
