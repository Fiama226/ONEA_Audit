import { FileUp, Users } from "lucide-react";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { fr } from "@/i18n/fr";
import { ImportCsvDialog } from "./ImportCsvDialog";
import { ImportDirectoryDialog } from "./ImportDirectoryDialog";

const t = fr.utilisateurs.import;

/** Boutons d'import (annuaire et CSV) de la liste des utilisateurs. */
export function ImportActions() {
  const [directoryOpen, setDirectoryOpen] = useState(false);
  const [csvOpen, setCsvOpen] = useState(false);
  return (
    <div className="flex flex-wrap gap-2 print:hidden">
      <Button type="button" variant="outline" onClick={() => setDirectoryOpen(true)}>
        <Users aria-hidden />
        {t.openDirectory}
      </Button>
      <Button type="button" variant="outline" onClick={() => setCsvOpen(true)}>
        <FileUp aria-hidden />
        {t.openCsv}
      </Button>
      {directoryOpen && (
        <ImportDirectoryDialog open={directoryOpen} onOpenChange={setDirectoryOpen} />
      )}
      {csvOpen && <ImportCsvDialog open={csvOpen} onOpenChange={setCsvOpen} />}
    </div>
  );
}
