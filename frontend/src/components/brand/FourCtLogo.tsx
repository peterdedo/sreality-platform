import logo4ctColor from "../../assets/logo-4ct-color.png";

type Variant = "onDark" | "onLight";

interface Props {
  variant?: Variant;
  /** Product name beside the 4ct logo (Sreality Platform). */
  showProductName?: boolean;
  showTagline?: boolean;
  compact?: boolean;
  className?: string;
}

/** Official 4ct color logo + optional product lockup. */
export function FourCtLogo({
  variant = "onDark",
  showProductName = true,
  showTagline = false,
  compact = false,
  className = "",
}: Props) {
  const productColor = variant === "onDark" ? "text-white" : "text-navy";
  const subColor = variant === "onDark" ? "text-white/55" : "text-ink-muted";
  const logoHeight = compact ? "h-8" : "h-10";

  return (
    <div className={`flex items-center gap-3 min-w-0 ${className}`.trim()}>
      <img
        src={logo4ctColor}
        alt="4ct"
        className={`${logoHeight} w-auto shrink-0 object-contain brand-logo`}
        draggable={false}
      />
      {(showProductName || showTagline) && (
        <div className="min-w-0 leading-tight border-l border-white/12 pl-3">
          {showProductName && (
            <p className={`font-semibold tracking-tight ${productColor} ${compact ? "text-sm" : "text-[15px]"}`}>
              Sreality Platform
            </p>
          )}
          {showTagline && (
            <p className={`${subColor} text-[11px] font-medium uppercase tracking-[0.14em] mt-0.5`}>
              Inteligence trhu nemovitostí
            </p>
          )}
        </div>
      )}
    </div>
  );
}
