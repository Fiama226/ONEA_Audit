import { useEffect, useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { ALERT_CLASS, FormField } from "@/components/form/FormField";
import { fr } from "@/i18n/fr";
import { formatDateTime } from "@/lib/dates";
import { useActionEvents, useActionTransition } from "../api";
import { EVENEMENT_LABELS } from "../labels";
import { fieldErrorsOf, generalErrorOf } from "../serverErrors";

const t = fr.suiviRegistre;

type Props = {
  actionId: string;
  missionId: string;
  /** `COMMENTER` figure dans les `actions_possibles` du serveur. */
  canComment: boolean;
};

function CommentForm({ actionId, missionId }: { actionId: string; missionId: string }) {
  const transition = useActionTransition();
  const [text, setText] = useState("");
  const [fieldError, setFieldError] = useState<string>();
  const [general, setGeneral] = useState<string>();
  const ref = useRef<HTMLTextAreaElement>(null);
  const [focus, setFocus] = useState(0);

  useEffect(() => {
    if (focus > 0) ref.current?.focus();
  }, [focus]);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setGeneral(undefined);
    const trimmed = text.trim();
    if (!trimmed) {
      setFieldError(t.commentRequired);
      setFocus((n) => n + 1);
      return;
    }
    setFieldError(undefined);
    try {
      await transition.mutateAsync({ id: actionId, kind: "comment", text: trimmed, missionId });
      setText("");
    } catch (error) {
      const fields = fieldErrorsOf(error);
      setFieldError(fields.texte);
      setGeneral(generalErrorOf(error));
      if (fields.texte) setFocus((n) => n + 1);
    }
  }

  return (
    <form
      onSubmit={(e) => void submit(e)}
      noValidate
      aria-label={t.commentTitle}
      className="grid gap-3"
    >
      <FormField label={t.commentLabel} error={fieldError}>
        {(props) => (
          <Textarea
            {...props}
            ref={ref}
            rows={3}
            value={text}
            onChange={(e) => setText(e.target.value)}
          />
        )}
      </FormField>
      <div>
        <Button type="submit" variant="outline" disabled={transition.isPending}>
          {t.commentSend}
        </Button>
      </div>
      {general && (
        <p role="alert" className={ALERT_CLASS}>
          {general}
        </p>
      )}
    </form>
  );
}

/** Chronologie d'une action (du plus récent au plus ancien) et point d'avancement libre. */
export function ActionTimeline({ actionId, missionId, canComment }: Props) {
  const events = useActionEvents(actionId);
  const sorted = [...(events.data ?? [])].sort((a, b) => b.le.localeCompare(a.le));

  return (
    <section
      aria-labelledby="timeline-title"
      className="grid gap-4 rounded-lg border border-border p-5"
    >
      <h2 id="timeline-title" className="text-base font-semibold">
        {t.timelineTitle}
      </h2>
      {canComment && (
        <div className="grid gap-2">
          <h3 className="text-sm font-medium">{t.commentTitle}</h3>
          <CommentForm actionId={actionId} missionId={missionId} />
        </div>
      )}
      {events.isError ? (
        <p role="alert" className={ALERT_CLASS}>
          {t.timelineLoadError}
        </p>
      ) : events.isLoading ? (
        <p role="status" className="text-sm text-text-muted">
          {fr.common.loading}
        </p>
      ) : sorted.length === 0 ? (
        <p className="text-sm text-text-muted">{t.timelineNone}</p>
      ) : (
        <ol className="grid gap-3">
          {sorted.map((event) => (
            <li key={event.id} className="grid gap-0.5 border-l-2 border-border pl-3 text-sm">
              <span className="font-medium">{EVENEMENT_LABELS[event.type]}</span>
              {event.texte && <span className="whitespace-pre-wrap">{event.texte}</span>}
              <span className="text-xs text-text-muted">
                <time dateTime={event.le}>{formatDateTime(event.le)}</time>
                {event.par && ` · ${t.timelineBy.replace("{name}", event.par.nom_complet)}`}
                {event.pour_compte_de &&
                  ` · ${t.timelineOnBehalf.replace("{name}", event.pour_compte_de.nom_complet)}`}
              </span>
            </li>
          ))}
        </ol>
      )}
    </section>
  );
}
