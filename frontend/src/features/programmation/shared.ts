/**
 * Seul point d'import des helpers partagés que le lot 3 déplace : après la tâche 6 du lot 3,
 * seuls ces chemins changent (`@/api/allPages`, `@/api/formErrors`, `@/components/form/*`,
 * `@/components/ListIncompleteAlert`).
 */
export { fetchAllPages, type AllPages } from "@/api/allPages";
export { applyApiErrors } from "@/api/formErrors";
export { FormField, ALERT_CLASS } from "@/components/form/FormField";
export { NativeSelect } from "@/components/form/NativeSelect";
export { ListIncompleteAlert } from "@/components/ListIncompleteAlert";
export { useAllProcesses } from "@/features/referentiel/allPages";
export { ConfirmDeleteDialog } from "@/features/referentiel/components/ConfirmDeleteDialog";
