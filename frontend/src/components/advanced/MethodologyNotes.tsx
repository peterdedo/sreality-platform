import { cs } from "../../locale/cs";

export function MethodologyNotes() {
  return (
    <section className="panel">
      <h2 className="font-semibold mb-3">{cs.advanced.metodologie.titulek}</h2>
      <ul className="list-disc list-inside space-y-2 text-sm text-ink">
        {cs.advanced.metodologie.text.map((line, i) => (
          <li key={i}>{line}</li>
        ))}
      </ul>
      <p className="text-xs text-ink-muted/70 mt-4">
        Podrobná metodika (anglicky, pro vývojáře): <code>docs/METHODOLOGY.md</code>
      </p>
    </section>
  );
}
