/* "What follows X?" — the one card that may use the word "because" nowhere.

Three numbers, always together: the count of sessions it followed, the count of
comparable days it did not, and one fixed verdict word. No percentage alone, no
interval, no p-value: at diary-sized N those read as precision the data does not
have. The server owns the gate and the vocabulary (app/insights/association.py);
this component only renders it, and says what is missing when the gate refuses.
*/

import type { Associations, Finding, GateCount } from "../api/types";
import { useI18n } from "../i18n";
import { gateLabel, verdictLabel } from "../lib/enums";
import type { Translate } from "../lib/timeLabels";

const VERDICT_STYLE: Record<string, string> = {
  "worth a look": "border-symptom/40 bg-symptom/10 text-symptom-ink",
  "looks like chance": "border-line bg-canvas text-muted",
  "nothing found": "border-physio/30 bg-physio/10 text-physio-ink",
};

function FindingRow({ finding, windowLabel }: { finding: Finding; windowLabel: string }) {
  const { t } = useI18n();
  return (
    <li className="row-enter rounded-xl bg-canvas p-3">
      <p className="text-sm leading-snug">
        <strong>{finding.symptom_name}</strong> {t("assoc.followed")}{" "}
        <strong>{t("assoc.ratioSessions", { hits: finding.hits, sessions: finding.sessions })}</strong>{" "}
        {t("assoc.sessionsOf")} {finding.exposure_name}{" "}
        {t("assoc.withinWindow", { window: windowLabel })} {t("assoc.controlLead")}{" "}
        <strong>
          {t("assoc.ratioTimes", { hits: finding.control_hits, windows: finding.control_windows })}
        </strong>{" "}
        {t("assoc.timesEnd")}
      </p>
      <p
        className={`mt-2 inline-block rounded-full border px-2.5 py-1 text-xs font-bold ${
          VERDICT_STYLE[finding.verdict] ?? VERDICT_STYLE["looks like chance"]
        }`}
      >
        {verdictLabel(finding.verdict, t)}
      </p>
      {finding.default_severity_hits > 0 ? (
        <p className="mt-2 text-xs text-muted">
          {t("assoc.defaultSeverity", { count: finding.default_severity_hits })}
        </p>
      ) : null}
    </li>
  );
}

/** Why the card could not answer for some pairs. Said in words, counted once. */
function gateSentence(gates: GateCount[], t: Translate): string | null {
  if (gates.length === 0) return null;
  const parts = gates.map((item) =>
    t("assoc.gatePairs", { count: item.pairs, why: gateLabel(item.gate, t) }),
  );
  return t("assoc.gateLead", { parts: parts.join("; ") });
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
  const { t } = useI18n();
  const worthALook = data.findings.filter((finding) => finding.verdict === "worth a look");
  const gate = gateSentence(data.gates, t);

  return (
    <section className="mt-4 rounded-2xl border border-line bg-card p-4">
      <div className="flex items-baseline justify-between gap-3">
        <h2 className="text-sm font-extrabold tracking-tight">{t("card.associations")}</h2>
        <span className="text-xs text-muted">{t("assoc.rangeDays", { days: data.days })}</span>
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
            ? t("assoc.sufficiencyNone")
            : t("assoc.sufficiencyFew", {
                days: data.coverage.days_covered,
                symptoms: data.coverage.symptom_logs,
                range: data.days,
              })}
        </p>
      ) : worthALook.length === 0 ? (
        <p className="mt-3 text-sm text-muted">
          {t("assoc.nothingStandsOut", {
            window: windowLabel,
            count: data.pairs_examined,
          })}
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
            ? t("assoc.examined", {
                count: worthALook.length,
                total: data.pairs_examined,
                window: windowLabel,
              })
            : ""}
          {data.skipped_sessions > 0
            ? ` ${t("assoc.skipped", { count: data.skipped_sessions })}`
            : ""}
        </p>
      ) : null}
    </section>
  );
}
