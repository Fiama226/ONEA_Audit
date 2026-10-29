import type { ComponentType } from "react";
import type { ZoneProps } from "./index";

/**
 * Compléments rendus sous la zone d'une étape, par numéro d'étape (ex. l'onglet « Référentiel
 * d'audit » des lots 5 et 6). Les lots suivants y ajoutent leurs composants sans toucher à la page.
 */
export const ZONE_COMPLEMENTS: Record<number, ComponentType<ZoneProps>[]> = {};
