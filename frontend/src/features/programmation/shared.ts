/**
 * Seul point d'import des helpers partagés que le lot 3 déplace : après la tâche 6 du lot 3,
 * seuls ces chemins changent (`@/api/allPages`, `@/api/formErrors`, `@/components/form/*`,
 * `@/components/ListIncompleteAlert`).
 */
export { fetchAllPages, type AllPages } from "@/features/referentiel/allPages";
export { applyApiErrors } from "@/features/referentiel/formErrors";
export { FormField, ALERT_CLASS } from "@/features/referentiel/components/FormField";
export { NativeSelect } from "@/features/referentiel/components/NativeSelect";
export { ListIncompleteAlert } from "@/features/referentiel/components/ListIncompleteAlert";
export { useAllProcesses } from "@/features/referentiel/allPages";
export { ConfirmDeleteDialog } from "@/features/referentiel/components/ConfirmDeleteDialog";
