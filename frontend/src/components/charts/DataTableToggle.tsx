import { useId, useState } from "react";
import { Button } from "@/components/ui/button";
import { fr } from "@/i18n/fr";

export interface ChartTable {
  columns: string[];
  rows: (string | number)[][];
}

/** Bouton « Afficher le tableau » : alternative textuelle du graphique (vrai `<table>`). */
export function DataTableToggle({ caption, table }: { caption: string; table: ChartTable }) {
  const [open, setOpen] = useState(false);
  const id = useId();
  return (
    <div className="mt-3">
      <Button
        type="button"
        variant="outline"
        size="sm"
        aria-expanded={open}
        aria-controls={id}
        onClick={() => setOpen((v) => !v)}
      >
        {open ? fr.charts.hideTable : fr.charts.showTable}
      </Button>
      <div id={id}>
        {open && (
          <div className="mt-2 overflow-x-auto">
            <table className="w-full border-collapse text-sm">
              <caption className="pb-1 text-left font-medium">{caption}</caption>
              <thead>
                <tr>
                  {table.columns.map((c) => (
                    <th
                      key={c}
                      scope="col"
                      className="border-b border-border px-2 py-1 text-left font-medium text-text-muted"
                    >
                      {c}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {table.rows.map((r, i) => (
                  <tr key={i}>
                    {r.map((cell, j) =>
                      j === 0 ? (
                        <th
                          key={j}
                          scope="row"
                          className="border-b border-border px-2 py-1 text-left font-normal"
                        >
                          {cell}
                        </th>
                      ) : (
                        <td key={j} className="border-b border-border px-2 py-1 tabular-nums">
                          {typeof cell === "number" ? cell.toLocaleString("fr-FR") : cell}
                        </td>
                      ),
                    )}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
