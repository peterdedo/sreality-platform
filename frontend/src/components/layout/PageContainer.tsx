import type { PropsWithChildren, ReactNode } from "react";

export function PageContainer({
  title,
  subtitle,
  actions,
  children,
}: PropsWithChildren<{ title: string; subtitle?: string; actions?: ReactNode }>) {
  return (
    <main className="page-shell animate-fade-in">
      <header className="page-hero">
        <div className="page-hero__content">
          <p className="page-hero__eyebrow">{subtitle ?? "4ct · Datová inteligence"}</p>
          <h1 className="page-hero__title">{title}</h1>
          <div className="page-hero__rule" aria-hidden />
        </div>
        {actions && <div className="page-hero__actions">{actions}</div>}
      </header>
      <div className="page-shell__body">{children}</div>
    </main>
  );
}
