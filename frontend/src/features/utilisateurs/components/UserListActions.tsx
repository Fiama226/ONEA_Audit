import { FileUp, UserPlus } from "lucide-react";
import { useState } from "react";
import { useAccountRights } from "@/auth/useAccountRights";
import { Button } from "@/components/ui/button";
import { fr } from "@/i18n/fr";
import { ImportCsvDialog } from "./ImportCsvDialog";
import { NewAccountDialog } from "./NewAccountDialog";

/**
 * Actions de la liste des utilisateurs : « Nouvel agent » (droit « créer »), import CSV
 * (administrateur seulement). Chaque fenêtre est démontée à la fermeture : rien n'y survit,
 * en particulier aucun mot de passe temporaire.
 */
export function UserListActions() {
  const { isAdmin, rights } = useAccountRights();
  const [createOpen, setCreateOpen] = useState(false);
  const [csvOpen, setCsvOpen] = useState(false);
  if (!rights.creer && !isAdmin) return null;
  return (
    <div className="flex flex-wrap gap-2 print:hidden">
      <Button type="button" onClick={() => setCreateOpen(true)}>
        <UserPlus aria-hidden />
        {fr.utilisateurs.creation.open}
      </Button>
      {isAdmin && (
        <Button type="button" variant="outline" onClick={() => setCsvOpen(true)}>
          <FileUp aria-hidden />
          {fr.utilisateurs.import.openCsv}
        </Button>
      )}
      {createOpen && <NewAccountDialog open={createOpen} onOpenChange={setCreateOpen} />}
      {csvOpen && <ImportCsvDialog open={csvOpen} onOpenChange={setCsvOpen} />}
    </div>
  );
}
