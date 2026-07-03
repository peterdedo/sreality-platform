import type { PropsWithChildren } from "react";
import { useEffect, useRef, useState } from "react";

/** Mount children only when the placeholder enters the viewport — defers heavy API/render work. */
export function LazyMount({
  children,
  minHeight = 120,
  rootMargin = "200px 0px",
}: PropsWithChildren<{ minHeight?: number; rootMargin?: string }>) {
  const ref = useRef<HTMLDivElement>(null);
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    const node = ref.current;
    if (!node || visible) return;

    const observer = new IntersectionObserver(
      (entries) => {
        if (entries.some((e) => e.isIntersecting)) {
          setVisible(true);
          observer.disconnect();
        }
      },
      { rootMargin }
    );
    observer.observe(node);
    return () => observer.disconnect();
  }, [visible, rootMargin]);

  return (
    <div ref={ref} style={{ minHeight: visible ? undefined : minHeight }}>
      {visible ? children : null}
    </div>
  );
}
