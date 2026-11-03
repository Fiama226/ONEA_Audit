import { useState, type FormEvent } from "react";
import { downloadEvidence } from "@/api/download";
import { isApiError } from "@/api/errors";
import { ALERT_CLASS, FormField } from "@/components/form/FormField";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { formatDateTime } from "@/lib/dates";
import { fr } from "@/i18n/fr";
import { useEvidence, useRemoveEvidence, useUpdateEvidence } from "../api";
import type { Piece } from "../types";
import { ScrollRegion } from "@/components/ui/scroll-region";

const t = fr.accomplissement.evidence;
const r = fr.fiches;

function formatSize(octets: number): string {
  if (octets < 1024) return `${octets} o`;
  if (octets < 1024 * 1024) return `${(octets / 1024).toFixed(1).replace(".", ",")} Ko`;
  return `${(octets / (1024 * 1024)).toFixed(1).replace(".", ",")} Mo`;
}

type Props = { ficheId: string; missionId: string };

/** Pièces d'une fiche ; les actions affichées suivent `actions_possibles` (le serveur reste juge). */
export function EvidenceList({ ficheId, missionId }: Props) {
  const evidence = useEvidence(ficheId);
  const update = useUpdateEvidence();
  const remove = useRemoveEvidence();
  const [message, setMessage] = useState<string | null>(null);
  const [copied, setCopied] = useState<string | null>(null);
  const [renaming, setRenaming] = useState<Piece | null>(null);

  if (evidence.isPending) return <p role="status">{fr.accomplissement.loading}</p>;
  if (evidence.isError) {
    return (
      <p role="alert" className={ALERT_CLASS}>
        {fr.accomplissement.loadError}
      </p>
    );
  }
  const pieces = evidence.data.results;
  if (pieces.length === 0) return <p className="text-sm text-text-muted">{t.empty}</p>;

  async function run(action: () => Promise<unknown>) {
    setMessage(null);
    try {
      await action();
    } catch (error) {
      setMessage(isApiError(error) ? error.detail : fr.errors.generic);
    }
  }

  async function copy(piece: Piece) {
    await navigator.clipboard?.writeText(piece.empreinte_sha256);
    setCopied(piece.id);
  }

  return (
    <div className="grid gap-2">
      {renaming && (
        <RenameDialog
          piece={renaming}
          onClose={() => setRenaming(null)}
          onSave={(libelle) =>
            update.mutateAsync({ id: renaming.id, ficheId, missionId, data: { libelle } })
          }
        />
      )}
      {message && (
        <p role="alert" className={ALERT_CLASS}>
          {message}
        </p>
      )}
      <ScrollRegion label={t.listLabel}>
        <table className="w-full text-left text-sm" aria-label={t.listLabel}>
          <thead>
            <tr className="border-b border-border text-xs text-text-muted">
              <th scope="col" className="py-2 pr-3">
                {t.number}
              </th>
              <th scope="col" className="py-2 pr-3">
                {t.name}
              </th>
              <th scope="col" className="py-2 pr-3">
                {t.fileName}
              </th>
              <th scope="col" className="py-2 pr-3">
                {t.size}
              </th>
              <th scope="col" className="py-2 pr-3">
                {t.fingerprint}
              </th>
              <th scope="col" className="py-2 pr-3">
                {t.depositedBy}
              </th>
              <th scope="col" className="py-2 pr-3">
                {t.depositedOn}
              </th>
              <th scope="col" className="py-2">
                {t.actions}
              </th>
            </tr>
          </thead>
          <tbody>
            {pieces.map((piece) => {
              const can = (action: string) => piece.actions_possibles.includes(action);
              return (
                <tr key={piece.id} className="border-b border-border align-top">
                  <td className="py-2 pr-3">{piece.numero}</td>
                  <td className="py-2 pr-3">{piece.libelle}</td>
                  <td className="py-2 pr-3 break-all">{piece.nom_fichier_original}</td>
                  <td className="py-2 pr-3 whitespace-nowrap">{formatSize(piece.taille_octets)}</td>
                  <td className="py-2 pr-3">
                    <code title={piece.empreinte_sha256} className="text-xs">
                      {piece.empreinte_sha256.slice(0, 12)}…
                    </code>{" "}
                    <Button
                      type="button"
                      variant="ghost"
                      size="sm"
                      onClick={() => void copy(piece)}
                      aria-label={`${t.copyFingerprint} (${piece.libelle})`}
                    >
                      {copied === piece.id ? t.fingerprintCopied : t.copyFingerprint}
                    </Button>
                  </td>
                  <td className="py-2 pr-3">{piece.deposee_par.nom_complet}</td>
                  <td className="py-2 pr-3 whitespace-nowrap">
                    {formatDateTime(piece.deposee_le)}
                  </td>
                  <td className="py-2">
                    <div className="flex flex-wrap gap-1">
                      {can("TELECHARGER") && (
                        <Button
                          type="button"
                          variant="outline"
                          size="sm"
                          onClick={() =>
                            void run(() => downloadEvidence(piece.id, piece.nom_fichier_original))
                          }
                        >
                          {t.download}
                        </Button>
                      )}
                      {can("MODIFIER") && (
                        <Button
                          type="button"
                          variant="outline"
                          size="sm"
                          onClick={() => setRenaming(piece)}
                        >
                          {t.rename}
                        </Button>
                      )}
                      {can("RETIRER") && (
                        <Button
                          type="button"
                          variant="outline"
                          size="sm"
                          onClick={() =>
                            void run(() => remove.mutateAsync({ id: piece.id, ficheId, missionId }))
                          }
                        >
                          {t.remove}
                        </Button>
                      )}
                    </div>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </ScrollRegion>
    </div>
  );
}

type RenameProps = {
  piece: Piece;
  onClose: () => void;
  onSave: (libelle: string) => Promise<unknown>;
};

/** Renommage du libellé d'une pièce (le fichier et son empreinte ne changent pas). */
function RenameDialog({ piece, onClose, onSave }: RenameProps) {
  const [value, setValue] = useState(piece.libelle);
  const [error, setError] = useState<string | undefined>();
  const [pending, setPending] = useState(false);

  async function submit(event: FormEvent) {
    event.preventDefault();
    const libelle = value.trim();
    if (!libelle) {
      setError(r.renameRequired);
      return;
    }
    if (libelle === piece.libelle) {
      onClose();
      return;
    }
    setPending(true);
    try {
      await onSave(libelle);
      onClose();
    } catch (e) {
      setError(isApiError(e) ? (e.errors.libelle?.join(" ") ?? e.detail) : fr.errors.generic);
      setPending(false);
    }
  }

  return (
    <Dialog open onOpenChange={(open) => !open && !pending && onClose()}>
      <DialogContent>
        <form onSubmit={(e) => void submit(e)} noValidate className="grid gap-4">
          <DialogHeader>
            <DialogTitle>{r.renameTitle}</DialogTitle>
          </DialogHeader>
          <FormField label={r.renameLabel} error={error}>
            {(p) => (
              <Input
                {...p}
                value={value}
                maxLength={200}
                onChange={(e) => setValue(e.target.value)}
              />
            )}
          </FormField>
          <DialogFooter>
            <Button type="button" variant="outline" disabled={pending} onClick={onClose}>
              {fr.common.cancel}
            </Button>
            <Button type="submit" disabled={pending}>
              {r.renameSave}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
