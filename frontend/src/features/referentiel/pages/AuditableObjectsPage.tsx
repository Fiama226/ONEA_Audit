import { useRef, useState } from "react";
import { Pencil, Plus, Trash2 } from "lucide-react";
import { useSearchParams } from "react-router-dom";
import { useAuth } from "@/auth/useAuth";
import { EmptyState } from "@/components/EmptyState";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { fr } from "@/i18n/fr";
import { useAllProcesses } from "../allPages";
import { useAuditableTree, useDeleteAuditableObject } from "../api";
import { ListIncompleteAlert } from "../components/ListIncompleteAlert";
import {
  AuditableObjectFormDialog,
  type AuditableObjectTarget,
} from "../components/AuditableObjectFormDialog";
import { ConfirmDeleteDialog } from "../components/ConfirmDeleteDialog";
import { ALERT_CLASS } from "../components/FormField";
import { NativeSelect } from "../components/NativeSelect";
import { canEditAuditableObjects } from "../permissions";
import type { DomaineArbre, ObjetAuditable } from "../types";

const s = fr.refStructure;
const ITEM = "data-tree-item";

/** Flèches haut/bas, Début et Fin : déplacent le focus entre les boutons d'action de l'arbre. */
function onTreeKeyDown(e: KeyboardEvent) {
  const keys = ["ArrowDown", "ArrowUp", "Home", "End"];
  if (!keys.includes(e.key)) return;
  const items = Array.from(
    (e.currentTarget as HTMLElement).querySelectorAll<HTMLElement>(`[${ITEM}]`),
  );
  if (items.length === 0) return;
  const current = items.indexOf(document.activeElement as HTMLElement);
  let next = current;
  if (e.key === "ArrowDown") next = Math.min(items.length - 1, current + 1);
  else if (e.key === "ArrowUp") next = Math.max(0, current <= 0 ? 0 : current - 1);
  else if (e.key === "Home") next = 0;
  else next = items.length - 1;
  e.preventDefault();
  items[next]?.focus();
}

type Deletion = { id: string; nature: "DOMAINE" | "OPERATION"; libelle: string };

export function AuditableObjectsPage() {
  const { me } = useAuth();
  const editable = canEditAuditableObjects(me?.role ?? null);
  const [params, setParams] = useSearchParams();
  const processId = params.get("processus") ?? "";
  const processes = useAllProcesses({ ordering: "ordre" });
  const heading = useRef<HTMLHeadingElement>(null);
  const [deleteOpen, setDeleteOpen] = useState(false);
  const tree = useAuditableTree(processId || undefined);
  const remove = useDeleteAuditableObject();
  const [target, setTarget] = useState<AuditableObjectTarget | null>(null);
  const [toDelete, setToDelete] = useState<Deletion | null>(null);

  function choose(value: string) {
    const next = new URLSearchParams(params);
    if (value) next.set("processus", value);
    else next.delete("processus");
    setParams(next, { replace: true });
  }

  const domains = tree.data ?? [];
  const processList = processes.data?.results ?? [];
  const selectedProcess = processList.find((p) => p.id === processId);

  function actions(
    label: string,
    existing: ObjetAuditable | DomaineArbre,
    nature: "DOMAINE" | "OPERATION",
    parentId?: string,
  ) {
    return (
      <span className="flex gap-1 print:hidden">
        <Button
          type="button"
          variant="ghost"
          size="icon"
          {...{ [ITEM]: "" }}
          aria-label={`${s.editObject} ${label}`}
          onClick={() => setTarget({ processId, nature, parentId, existing })}
        >
          <Pencil aria-hidden />
        </Button>
        <Button
          type="button"
          variant="ghost"
          size="icon"
          {...{ [ITEM]: "" }}
          aria-label={`${s.deleteObject} ${label}`}
          onClick={() => {
            setToDelete({ id: existing.id, nature, libelle: label });
            setDeleteOpen(true);
          }}
        >
          <Trash2 aria-hidden />
        </Button>
      </span>
    );
  }

  let body;
  if (!processId) {
    body = (
      <EmptyState
        title={s.noProcessSelectedTitle}
        description={s.noProcessSelectedText}
        illustration={false}
      />
    );
  } else if (tree.isLoading) {
    body = <Skeleton role="status" aria-label={fr.common.loading} className="h-48 w-full" />;
  } else if (tree.isError) {
    body = (
      <div role="alert" className={ALERT_CLASS}>
        <p>{s.loadError}</p>
        <Button
          type="button"
          variant="outline"
          size="sm"
          className="mt-2"
          onClick={() => void tree.refetch()}
        >
          {fr.common.retry}
        </Button>
      </div>
    );
  } else if (domains.length === 0) {
    body = (
      <EmptyState
        title={s.noDomainTitle}
        description={editable ? s.noDomainTextEditor : s.noDomainTextReader}
        illustration={false}
      >
        {editable && (
          <Button type="button" onClick={() => setTarget({ processId, nature: "DOMAINE" })}>
            <Plus aria-hidden />
            {s.addDomain}
          </Button>
        )}
      </EmptyState>
    );
  } else {
    body = (
      <div
        className="rounded-lg border border-border bg-surface p-4"
        ref={(el) => {
          if (!el || !editable) return;
          el.addEventListener("keydown", onTreeKeyDown);
          return () => el.removeEventListener("keydown", onTreeKeyDown);
        }}
      >
        {editable && <p className="mb-3 text-xs text-text-muted print:hidden">{s.treeHint}</p>}
        <ul aria-label={s.treeLabel} className="grid gap-5">
          {domains.map((domain) => (
            <li key={domain.id}>
              <div className="flex items-center justify-between gap-3 border-b border-border pb-1">
                <h4 id={`dom-${domain.id}`} className="text-base font-semibold">
                  {domain.libelle}
                </h4>
                {editable && actions(domain.libelle, domain, "DOMAINE")}
              </div>
              {domain.description && (
                <p className="mt-1 text-sm text-text-muted">{domain.description}</p>
              )}
              {domain.operations.length === 0 ? (
                <p className="mt-2 pl-6 text-sm text-text-muted">{s.noOperations}</p>
              ) : (
                <ul aria-labelledby={`dom-${domain.id}`} className="mt-2 grid gap-1 pl-6">
                  {domain.operations.map((op) => (
                    <li key={op.id} className="flex items-center justify-between gap-3 text-sm">
                      <span>{op.libelle}</span>
                      {editable && actions(op.libelle, op, "OPERATION", domain.id)}
                    </li>
                  ))}
                </ul>
              )}
              {editable && (
                <div className="mt-2 pl-6 print:hidden">
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    {...{ [ITEM]: "" }}
                    onClick={() =>
                      setTarget({ processId, nature: "OPERATION", parentId: domain.id })
                    }
                  >
                    <Plus aria-hidden />
                    {s.addOperation}
                    <span className="sr-only"> - {domain.libelle}</span>
                  </Button>
                </div>
              )}
            </li>
          ))}
        </ul>
      </div>
    );
  }

  return (
    <div className="grid gap-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 ref={heading} tabIndex={-1} className="text-xl font-semibold outline-none">
          {fr.referentiel.pageObjets}
        </h2>
        {editable && processId && domains.length > 0 && (
          <Button
            type="button"
            className="print:hidden"
            onClick={() => setTarget({ processId, nature: "DOMAINE" })}
          >
            <Plus aria-hidden />
            {s.addDomain}
          </Button>
        )}
      </div>
      <div className="grid max-w-md gap-1.5 print:hidden">
        <Label htmlFor="obj-process">{s.processSelectorLabel}</Label>
        <NativeSelect id="obj-process" value={processId} onChange={(e) => choose(e.target.value)}>
          <option value="">{s.processSelectorPlaceholder}</option>
          {processes.isLoading && processId && (
            <option value={processId}>{fr.common.loading}</option>
          )}
          {processList.map((p) => (
            <option key={p.id} value={p.id}>
              {p.code} - {p.libelle}
            </option>
          ))}
        </NativeSelect>
        {processes.data && (
          <ListIncompleteAlert count={processes.data.count} loaded={processList.length} />
        )}
      </div>
      {processes.isError && (
        <div role="alert" className={ALERT_CLASS}>
          <p>{s.loadError}</p>
          <Button
            type="button"
            variant="outline"
            size="sm"
            className="mt-2"
            onClick={() => void processes.refetch()}
          >
            {fr.common.retry}
          </Button>
        </div>
      )}
      {selectedProcess && (
        <h3 className="text-base font-semibold">
          {selectedProcess.code} - {selectedProcess.libelle}
        </h3>
      )}
      {body}
      {editable && (
        <AuditableObjectFormDialog
          target={target}
          onOpenChange={(open) => !open && setTarget(null)}
        />
      )}
      {toDelete && (
        <ConfirmDeleteDialog
          open={deleteOpen}
          onOpenChange={setDeleteOpen}
          title={toDelete.nature === "DOMAINE" ? s.deleteDomainTitle : s.deleteOperationTitle}
          description={`${toDelete.libelle}. ${s.deleteObjectText}`}
          onConfirm={() => remove.mutateAsync(toDelete.id)}
          restoreFocus={() => heading.current?.focus()}
        />
      )}
    </div>
  );
}
