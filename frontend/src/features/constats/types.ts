import type { components } from "@/api/schema";

type S = components["schemas"];

export type Constat = S["Constat"];
export type ConstatResume = S["ConstatResume"];
export type ConstatInput = S["ConstatRequest"];
export type ConstatUpdate = S["PatchedConstatRequest"];
export type StatutConstat = S["StatutConstatEnum"];
export type CategorieCause = S["CategorieCauseEnum"];
export type PrioriteRecommandation = S["PrioriteRecommandationEnum"];
export type PositionAudite = S["PositionAuditeEnum"];

export type CauseConstat = S["CauseConstat"];
export type Recommandation = S["Recommandation"];
export type RecommandationListe = S["RecommandationListe"];

export type ReponseAudite = S["ReponseAudite"];
export type ReponseInput = S["ReponseRequestRequest"];

/** Actions de transition d'un constat (routes `/findings/{id}/<action>/`). */
export type ConstatAction = "submit" | "validate" | "return" | "reopen";
