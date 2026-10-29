import { useRef, useState } from "react";
import { isApiError } from "@/api/errors";
import { ALERT_CLASS } from "@/components/form/FormField";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import type { Mission } from "@/features/missions/types";
import { fr } from "@/i18n/fr";
import { useSaveSegregationGrid } from "../api";
import { ROLE_TACHE_CODES, ROLE_TACHE_LABELS } from "../labels";
import {
  LABEL_MAX,
  MAX_ACTORS,
  MAX_TASKS,
  segregationGridSchema,
} from "../schemas/segregationGrid";
import type { GrilleSeparation, RoleTache } from "../types";

const t = fr.analyseIII;
const ROLES = Object.keys(ROLE_TACHE_LABELS) as RoleTache[];

type Props = {
  mission: Mission;
  processus: Mission["processus_detail"][number];
  grid?: GrilleSeparation;
  editable: boolean;
};

type Cells = Record<string, RoleTache[]>;
const key = (i: number, j: number) => `${i}:${j}`;

function toCells(grid?: GrilleSeparation): Cells {
  const cells: Cells = {};
  for (const c of grid?.cellules ?? []) cells[key(c.tache, c.acteur)] = [...c.roles];
  return cells;
}

/** Retire la ligne (axis "tache") ou la colonne (axis "acteur") `index` et décale les indices. */
function dropIndex(cells: Cells, axis: "tache" | "acteur", index: number): Cells {
  const next: Cells = {};
  for (const [k, roles] of Object.entries(cells)) {
    const [i = 0, j = 0] = k.split(":").map(Number);
    const target = axis === "tache" ? i : j;
    if (target === index) continue;
    const shifted = target > index ? target - 1 : target;
    next[axis === "tache" ? key(shifted, j) : key(i, shifted)] = roles;
  }
  return next;
}

function messagesOf(e: unknown): string[] {
  if (!isApiError(e)) return [fr.errors.generic];
  const lines = Object.values(e.errors).flat();
  return lines.length > 0 ? lines : [e.detail];
}

export function SegregationGridEditor({ processus, mission, grid, editable }: Props) {
  const save = useSaveSegregationGrid();
  const [taches, setTaches] = useState<string[]>(grid?.taches ?? []);
  const [acteurs, setActeurs] = useState<string[]>(grid?.acteurs ?? []);
  const [cells, setCells] = useState<Cells>(() => toCells(grid));
  const [comment, setComment] = useState(grid?.commentaire ?? "");
  const [dirty, setDirty] = useState(false);
  const [saved, setSaved] = useState(false);
  const [errors, setErrors] = useState<string[]>([]);
  const errorRef = useRef<HTMLDivElement>(null);
  const writable = editable && !grid?.etape_close;
  const errorId = `grid-${processus.id}-errors`;

  function touch() {
    setDirty(true);
    setSaved(false);
  }

  function toggle(i: number, j: number, role: RoleTache, on: boolean) {
    touch();
    setCells((prev) => {
      const current = prev[key(i, j)] ?? [];
      const roles = on
        ? ROLES.filter((r) => r === role || current.includes(r))
        : current.filter((r) => r !== role);
      return { ...prev, [key(i, j)]: roles };
    });
  }

  function fail(lines: string[]) {
    setErrors(lines);
    setTimeout(() => errorRef.current?.focus(), 0);
  }

  async function onSave() {
    setErrors([]);
    const parsed = segregationGridSchema.safeParse({ taches, acteurs });
    if (!parsed.success) {
      fail([...new Set(parsed.error.issues.map((i) => i.message))]);
      return;
    }
    const cellules = Object.entries(cells)
      .filter(([, roles]) => roles.length > 0)
      .map(([k, roles]) => {
        const [tache = 0, acteur = 0] = k.split(":").map(Number);
        return { tache, acteur, roles };
      });
    try {
      await save.mutateAsync({
        data: {
          mission: mission.id,
          processus: processus.id,
          taches: parsed.data.taches,
          acteurs: parsed.data.acteurs,
          cellules,
          commentaire: comment,
        },
      });
      setTaches(parsed.data.taches);
      setActeurs(parsed.data.acteurs);
      setDirty(false);
      setSaved(true);
    } catch (e) {
      fail(messagesOf(e));
    }
  }

  const heading = (
    <h5 className="text-sm font-semibold">{`${processus.code} — ${processus.libelle}`}</h5>
  );

  if (!grid && !writable) {
    return (
      <article className="grid gap-1 rounded-md border border-border p-4">
        {heading}
        <p className="text-sm text-text-muted">{t.gridEmpty}</p>
      </article>
    );
  }

  const taskName = (i: number) =>
    taches[i]?.trim() || t.gridUnnamedTask.replace("{n}", String(i + 1));
  const actorName = (j: number) =>
    acteurs[j]?.trim() || t.gridUnnamedActor.replace("{n}", String(j + 1));
  const analyse = grid?.analyse;
  const alerts = [
    ...(analyse?.cumuls ?? []).map((c) =>
      t.gridCumul
        .replace("{actor}", c.acteur)
        .replace("{roles}", c.roles.map((r) => t.roleVerbs[r]).join(` ${t.and} `))
        .replace("{task}", c.tache),
    ),
    ...(analyse?.taches_sans_acteur ?? []).map((x) => t.gridNoActor.replace("{task}", x)),
    ...(analyse?.taches_multi_executants ?? []).map((x) =>
      t.gridMultiExecutants.replace("{task}", x),
    ),
  ];

  return (
    <article className="grid gap-3 rounded-md border border-border p-4">
      <style media="print">{"@page { size: A4 landscape; }"}</style>
      {heading}
      <div className="overflow-x-auto">
        <table
          className="w-full border-collapse text-sm"
          aria-describedby={errors.length > 0 ? errorId : undefined}
        >
          <caption className="sr-only">
            {t.gridCaption.replace("{process}", processus.code)}
          </caption>
          <thead>
            <tr>
              <th scope="col" className="border border-border p-2 text-left">
                {t.gridTaskHeader}
              </th>
              {acteurs.map((_, j) => (
                <th key={j} scope="col" className="border border-border p-2 text-left align-top">
                  {writable ? (
                    <div className="grid gap-1">
                      <Input
                        value={acteurs[j]}
                        maxLength={LABEL_MAX}
                        aria-label={t.gridActorName.replace("{n}", String(j + 1))}
                        onChange={(e) => {
                          touch();
                          setActeurs((a) => a.map((v, k) => (k === j ? e.target.value : v)));
                        }}
                      />
                      <Button
                        type="button"
                        variant="ghost"
                        size="sm"
                        className="print:hidden"
                        onClick={() => {
                          touch();
                          setActeurs((a) => a.filter((_, k) => k !== j));
                          setCells((c) => dropIndex(c, "acteur", j));
                        }}
                      >
                        {t.gridRemoveActor.replace("{n}", String(j + 1))}
                      </Button>
                    </div>
                  ) : (
                    acteurs[j]
                  )}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {taches.map((_, i) => (
              <tr key={i}>
                <th scope="row" className="border border-border p-2 text-left align-top">
                  {writable ? (
                    <div className="grid gap-1">
                      <Input
                        value={taches[i]}
                        maxLength={LABEL_MAX}
                        aria-label={t.gridTaskName.replace("{n}", String(i + 1))}
                        onChange={(e) => {
                          touch();
                          setTaches((a) => a.map((v, k) => (k === i ? e.target.value : v)));
                        }}
                      />
                      <Button
                        type="button"
                        variant="ghost"
                        size="sm"
                        className="print:hidden"
                        onClick={() => {
                          touch();
                          setTaches((a) => a.filter((_, k) => k !== i));
                          setCells((c) => dropIndex(c, "tache", i));
                        }}
                      >
                        {t.gridRemoveTask.replace("{n}", String(i + 1))}
                      </Button>
                    </div>
                  ) : (
                    taches[i]
                  )}
                </th>
                {acteurs.map((_, j) => {
                  const roles = cells[key(i, j)] ?? [];
                  return (
                    <td key={j} className="border border-border p-2 align-top">
                      {writable ? (
                        <div className="flex flex-wrap gap-2">
                          {ROLES.map((r) => {
                            const name = t.gridCell
                              .replace("{task}", taskName(i))
                              .replace("{actor}", actorName(j))
                              .replace("{role}", ROLE_TACHE_LABELS[r]);
                            return (
                              <span key={r} className="flex items-center gap-1" title={name}>
                                <Checkbox
                                  aria-label={name}
                                  checked={roles.includes(r)}
                                  onCheckedChange={(on) => toggle(i, j, r, on === true)}
                                />
                                <span aria-hidden="true" className="text-xs">
                                  {ROLE_TACHE_CODES[r]}
                                </span>
                              </span>
                            );
                          })}
                        </div>
                      ) : (
                        roles.map((r) => ROLE_TACHE_CODES[r]).join(", ")
                      )}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="text-xs text-text-muted">{t.gridLegend}</p>
      {writable && (
        <div className="flex flex-wrap gap-2 print:hidden">
          <Button
            type="button"
            variant="outline"
            size="sm"
            disabled={taches.length >= MAX_TASKS}
            onClick={() => {
              touch();
              setTaches((a) => [...a, ""]);
            }}
          >
            {t.gridAddTask}
          </Button>
          <Button
            type="button"
            variant="outline"
            size="sm"
            disabled={acteurs.length >= MAX_ACTORS}
            onClick={() => {
              touch();
              setActeurs((a) => [...a, ""]);
            }}
          >
            {t.gridAddActor}
          </Button>
        </div>
      )}
      {writable ? (
        <div className="grid gap-1.5">
          <Label htmlFor={`grid-${processus.id}-comment`}>{t.gridComment}</Label>
          <Textarea
            id={`grid-${processus.id}-comment`}
            value={comment}
            maxLength={5000}
            onChange={(e) => {
              touch();
              setComment(e.target.value);
            }}
          />
        </div>
      ) : (
        comment && <p className="whitespace-pre-wrap text-sm">{comment}</p>
      )}
      {errors.length > 0 && (
        <div id={errorId} ref={errorRef} tabIndex={-1} role="alert" className={ALERT_CLASS}>
          {errors.map((line) => (
            <p key={line}>{line}</p>
          ))}
        </div>
      )}
      {dirty && <p className="text-xs text-text-muted">{t.gridDirty}</p>}
      {alerts.length > 0 && (
        <section aria-label={t.gridAlerts}>
          <ul className="grid list-disc gap-1 pl-5 text-sm text-destructive">
            {alerts.map((a) => (
              <li key={a}>{a}</li>
            ))}
          </ul>
        </section>
      )}
      {saved && (
        <p role="status" className="text-sm text-text-muted">
          {t.gridSaved}
        </p>
      )}
      {writable && (
        <div className="print:hidden">
          <Button type="button" disabled={save.isPending} onClick={() => void onSave()}>
            {t.gridSave}
          </Button>
        </div>
      )}
    </article>
  );
}
