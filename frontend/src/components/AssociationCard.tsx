/* "What follows X?" — the one card that may use the word "because" nowhere.

Three numbers, always together: the count of sessions it followed, the count of
comparable days it did not, and one fixed verdict word. No percentage alone, no
interval, no p-value: at diary-sized N those read as precision the data does not
have. The server owns the gate and the vocabulary (app/insights/association.py);
this component only renders it, and says what is missing when the gate refuses.
*/

import type { Associations, Finding, GateCount } from "../api/types";

const VERDICT_STYLE: Record<string, string> = {
  "worth a look": "border-symptom/40 bg-symptom/10 text-symptom-ink",
  "looks like chance": "border-line bg-canvas text-muted",
  "nothing found": "border-physio/30 bg-physio/10 text-physio-ink",
};

// Noun phrases, not sentences: they are joined into one line ("21 pairs — too few
// follow-ons...; 1 pair — no comparable day"), and full stops inside that read wrong.
const GATE_LINE: Record<string, string> = {
  too_few_sessions: "too few sessions of this to say anything",
  too_few_hits: "too few follow-ons to tell a pattern from a coincidence",
  no_comparable_windows: "no comparable day, because this is logged almost every day",
};

function FindingRow({ finding, windowLabel }: { finding: Finding; windowLabel: string }) {
  return (
    <li className="row-enter rounded-xl bg-canvas p-3">
      <p className="text-sm leading-snug">
        <strong>{finding.symptom_name}</strong> followed{" "}
        <strong>
          {finding.hits} of {finding.sessions}
        </strong>{" "}
        {finding.exposure_name} sessions within {windowLabel}. On comparable days with
        none, it happened{" "}
        <strong>
          {finding.control_hits} of {finding.control_windows}
        </strong>{" "}
        times.
      </p>
      <p
        className={`mt-2 inline-block rounded-full border px-2.5 py-1 text-xs font-bold ${
          VERDICT_STYLE[finding.verdict] ?? VERDICT_STYLE["looks like chance"]
        }`}
      >
        {finding.verdict}
      </p>
      {finding.default_severity_hits > 0 ? (
        <p className="mt-2 text-xs text-muted">
          {finding.default_severity_hits} of those symptom entries used the default
          severity, not a chosen one.
        </p>
      ) : null}
    </li>
  );
}

/** Why the card could not answer for some pairs. Said in words, counted once. */
function gateSentence(gates: GateCount[]): string | null {
  if (gates.length === 0) return null;
  const parts = gates.map(
    (item) =>
      `${item.pairs} pair${item.pairs === 1 ? "" : "s"} — ${GATE_LINE[item.gate] ?? "not enough to tell"}`,
  );
  return `Could not compare ${parts.join("; ")}.`;
}

export function AssociationCard({
  data,
  windowLabel,
  onWindow,
}: {
  data: Associations;
  windowLabel: string;
  onWindow: (label: string) => void;
}) {
  const worthALook = data.findings.filter((finding) => finding.verdict === "worth a look");
  const gate = gateSentence(data.gates);

  return (
    <section className="mt-4 rounded-2xl border border-line bg-card p-4">
      <div className="flex items-baseline justify-between gap-3">
        <h2 className="text-sm font-extrabold tracking-tight">What follows a session?</h2>
        <span className="text-xs text-muted">{data.days}d</span>
      </div>

      <div className="mt-3 flex gap-1.5">
        {data.windows.map((option) => (
          <button
            key={option.label}
            type="button"
            onClick={() => onWindow(option.label)}
            aria-pressed={option.label === windowLabel}
            className={`rounded-full border px-3 py-1.5 text-xs font-bold ${
              option.label === windowLabel
                ? "border-symptom bg-symptom text-white"
                : "border-line text-muted"
            }`}
          >
            {option.label}
          </button>
        ))}
      </div>

      {data.sufficiency !== "enough" ? (
        <p className="mt-3 text-sm text-muted">
          {data.sufficiency === "none"
            ? "Nothing logged in this range yet. This card needs a diary, not a guess."
            : `Not enough yet: ${data.coverage.days_covered} logged days and ${data.coverage.symptom_logs} symptom entries in ${data.days} days. Keep logging — the maths will not guess.`}
        </p>
      ) : worthALook.length === 0 ? (
        <p className="mt-3 text-sm text-muted">
          Nothing here stands out at {windowLabel}, across {data.pairs_examined} pair
          {data.pairs_examined === 1 ? "" : "s"} of definitions. That is a result, not a
          failure: it means nothing followed a session more often than on comparable days.
        </p>
      ) : (
        <ul className="mt-3 space-y-2">
          {worthALook.map((finding) => (
            <FindingRow
              key={`${finding.exposure_id}-${finding.symptom_id}`}
              finding={finding}
              windowLabel={windowLabel}
            />
          ))}
        </ul>
      )}

      {gate ? <p className="mt-3 text-xs text-faint">{gate}</p> : null}

      {/* Only when something was found: the "nothing stands out" line above already
          says how many pairs were examined, and repeating it is noise. */}
      {data.sufficiency === "enough" && (worthALook.length > 0 || data.skipped_sessions > 0) ? (
        <p className="mt-3 text-xs text-faint">
          {worthALook.length > 0
            ? `${worthALook.length} of ${data.pairs_examined} pairs examined, at ${windowLabel}.`
            : ""}
          {data.skipped_sessions > 0
            ? ` ${data.skipped_sessions} session${data.skipped_sessions === 1 ? "" : "s"} you logged as skipped were left out.`
            : ""}
        </p>
      ) : null}
    </section>
  );
}
