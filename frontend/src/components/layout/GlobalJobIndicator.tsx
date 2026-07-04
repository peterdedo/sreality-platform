import { Link } from "react-router-dom";
import { cs } from "../../locale/cs";
import { useGlobalJobStatus } from "../../hooks/useGlobalJobStatus";

export function GlobalJobIndicator() {
  const { active, label, linkTo } = useGlobalJobStatus();

  if (!active || !label) {
    return null;
  }

  return (
    <Link
      to={linkTo}
      className="global-job-indicator"
      title={cs.jobs.napoveda}
    >
      <span className="global-job-indicator__dot" aria-hidden />
      <span className="global-job-indicator__label">{label}</span>
    </Link>
  );
}
