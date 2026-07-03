import type { ReactNode } from "react";

type Props = {
  href: string | null | undefined;
  children: ReactNode;
  className?: string;
};

export function SrealityLink({ href, children, className = "" }: Props) {
  if (!href) {
    return null;
  }

  return (
    <a
      href={href}
      target="_blank"
      rel="noopener noreferrer"
      className={className}
      onClick={(event) => event.stopPropagation()}
    >
      {children}
    </a>
  );
}
