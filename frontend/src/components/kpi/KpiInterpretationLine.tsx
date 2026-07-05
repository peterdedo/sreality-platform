import { Link } from "react-router-dom";
import { stateChipLabel } from "../../kpi/model";
import { cs } from "../../locale/cs";
import type { KpiInterpretation } from "../../kpi/types";

type Props = {
  interpretation: KpiInterpretation;
};

export function KpiInterpretationLine({ interpretation }: Props) {
  const { meaning, benchmark, direction, directionLabel, nextStep, nextStepLink, limited, state, confidence } =
    interpretation;

  // Prefer the explicit model chip (baseline / ingest / málo historie /
  // orientační); fall back to the legacy "Omezený vzorek" only for readings
  // not yet migrated to the interpretation model.
  const chip =
    state && confidence ? stateChipLabel(state, confidence) : limited ? cs.kpiInterpret.stavChip.orientacni : null;

  return (
    <div className="kpi-interp">
      <div className="kpi-interp__head">
        <span className={`kpi-interp__badge kpi-interp__badge--${direction}`}>{directionLabel}</span>
        {chip && <span className="kpi-interp__limited">{chip}</span>}
      </div>
      <p className="kpi-interp__meaning">{meaning}</p>
      {benchmark && <p className="kpi-interp__benchmark">{benchmark}</p>}
      {nextStep && (
        <p className="kpi-interp__next">
          {nextStepLink ? (
            <>
              {nextStep.replace(/\s→$/, "")}{" "}
              <Link to={nextStepLink.to} className="link-brand font-medium">
                {nextStepLink.label} →
              </Link>
            </>
          ) : (
            nextStep
          )}
        </p>
      )}
    </div>
  );
}

export function PanelInsight({ interpretation }: Props) {
  return (
    <div className="panel-insight">
      <KpiInterpretationLine interpretation={interpretation} />
    </div>
  );
}
