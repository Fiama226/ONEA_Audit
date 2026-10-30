import { Copy } from "lucide-react";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import {
  Table,
  TableBody,
  TableCaption,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { fr } from "@/i18n/fr";
import type { DocumentType } from "../types";

const t = fr.documentsAdmin;

type Champ = DocumentType["champs"][number];

/** Balise à coller dans Word : `{{ a.b }}` pour un champ, `{%tr for l in a.b %}` pour une liste. */
export function tagFor(path: string, champ: Champ): string | null {
  if (champ.type === "bloc") return null;
  if (champ.type === "liste") return `{%tr for l in ${path} %}`;
  return `{{ ${path} }}`;
}

/** `path` : chemin de la balise (variable de boucle `l` sous une liste) ; `full` : chemin complet, unique. */
type Row = { champ: Champ; path: string; full: string; depth: number };

function flatten(champs: Champ[], prefix: string, fullPrefix: string, depth: number): Row[] {
  return champs.flatMap((champ) => {
    const path = prefix ? `${prefix}.${champ.nom}` : champ.nom;
    const full = fullPrefix ? `${fullPrefix}.${champ.nom}` : champ.nom;
    // Dans une boucle, les champs enfants s'écrivent avec la variable de boucle `l`.
    const childPrefix = champ.type === "liste" ? "l" : path;
    return [{ champ, path, full, depth }, ...flatten(champ.enfants, childPrefix, full, depth + 1)];
  });
}

export function ContractFieldsPanel({ type }: { type: DocumentType }) {
  const [message, setMessage] = useState("");
  const rows = flatten(type.champs, "", "", 0);

  async function copy(tag: string) {
    try {
      await navigator.clipboard.writeText(tag);
      setMessage(t.copied);
      setTimeout(() => setMessage(""), 3000);
    } catch {
      setMessage(t.copyFailed);
    }
  }

  return (
    <section aria-labelledby="contract-title" className="grid gap-3">
      <div>
        <h2 id="contract-title" className="text-lg font-semibold">
          {t.contractTitle}{" "}
          <span className="text-sm text-text-muted">
            ({t.contractVersion(type.contrat_version)})
          </span>
        </h2>
        <p className="mt-1 text-sm text-text-muted">{t.contractIntro}</p>
        <p className="mt-1 text-sm">
          {t.contractDoc}{" "}
          <code className="font-mono text-xs">docs/documents/contrats/{type.code}.md</code>
        </p>
      </div>
      <p role="status" className="text-sm text-text-muted">
        {message}
      </p>
      {rows.length === 0 ? (
        <p className="text-sm text-text-muted">{t.contractEmpty}</p>
      ) : (
        <Table>
          <TableCaption className="sr-only">{t.contractCaption}</TableCaption>
          <TableHeader>
            <TableRow>
              <TableHead>{t.colTag}</TableHead>
              <TableHead>{t.colType}</TableHead>
              <TableHead>{t.colDescription}</TableHead>
              <TableHead>
                <span className="sr-only">{fr.common.actions}</span>
              </TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {rows.map(({ champ, path, full, depth }) => {
              const tag = tagFor(path, champ);
              return (
                <TableRow key={full}>
                  <TableCell style={{ paddingLeft: `${0.5 + depth * 1.25}rem` }}>
                    <code className="font-mono text-xs">{champ.nom}</code>
                  </TableCell>
                  <TableCell>{t.fieldTypes[champ.type]}</TableCell>
                  <TableCell>{champ.description}</TableCell>
                  <TableCell>
                    {tag && (
                      <Button
                        type="button"
                        variant="ghost"
                        size="sm"
                        aria-label={t.copyTag(full)}
                        onClick={() => void copy(tag)}
                      >
                        <Copy aria-hidden="true" className="size-3.5" />
                        {t.copy}
                      </Button>
                    )}
                  </TableCell>
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
      )}
    </section>
  );
}
