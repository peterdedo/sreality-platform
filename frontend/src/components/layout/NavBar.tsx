import { useEffect, useState } from "react";
import { NavLink, useLocation } from "react-router-dom";
import { FourCtLogo } from "../brand/FourCtLogo";
import { cs } from "../../locale/cs";

const links = [
  { to: "/", label: cs.nav.prehledTrhu },
  { to: "/nabidky", label: cs.nav.nabidky },
  { to: "/mapa", label: cs.nav.mapa },
  { to: "/analytika", label: cs.nav.analytika },
  { to: "/historie-cen", label: cs.nav.historieCen },
  { to: "/pokrocile-analyzy", label: cs.nav.pokroziteAnalyzy },
  { to: "/sprava-scrapingu", label: cs.nav.spravaScrapingu },
];

function NavLinks({
  onNavigate,
  className,
}: {
  onNavigate?: () => void;
  className: string;
}) {
  return (
    <nav className={className} aria-label={cs.brand.hlavniNavigace}>
      {links.map((link) => (
        <NavLink
          key={link.to}
          to={link.to}
          end={link.to === "/"}
          onClick={onNavigate}
          className={({ isActive }) => `app-nav__link${isActive ? " app-nav__link--active" : ""}`}
        >
          <span className="app-nav__label">{link.label}</span>
          <span className="app-nav__indicator" aria-hidden />
        </NavLink>
      ))}
    </nav>
  );
}

export function NavBar() {
  const [menuOpen, setMenuOpen] = useState(false);
  const location = useLocation();

  useEffect(() => {
    setMenuOpen(false);
  }, [location.pathname]);

  useEffect(() => {
    document.body.classList.toggle("nav-drawer-open", menuOpen);
    return () => document.body.classList.remove("nav-drawer-open");
  }, [menuOpen]);

  return (
    <header className="app-header sticky top-0 z-50">
      <div className="app-header__glow" aria-hidden />
      <div className="app-header__inner">
        <NavLink to="/" end className="brand-lockup group" aria-label={cs.brand.domovskaStranka}>
          <FourCtLogo variant="onDark" showProductName showTagline={false} />
          <span className="brand-lockup__tagline hidden xl:block">{cs.brand.tagline}</span>
        </NavLink>

        <NavLinks className="app-nav app-nav--desktop" />

        <button
          type="button"
          className="app-nav-toggle lg:hidden"
          aria-expanded={menuOpen}
          aria-controls="mobile-nav-drawer"
          aria-label={menuOpen ? cs.nav.zavritMenu : cs.nav.otevritMenu}
          onClick={() => setMenuOpen((open) => !open)}
        >
          <span className="app-nav-toggle__bar" aria-hidden />
          <span className="app-nav-toggle__bar" aria-hidden />
          <span className="app-nav-toggle__bar" aria-hidden />
        </button>
      </div>

      {menuOpen && (
        <>
          <button
            type="button"
            className="app-nav-backdrop lg:hidden"
            aria-label={cs.nav.zavritMenu}
            onClick={() => setMenuOpen(false)}
          />
          <div id="mobile-nav-drawer" className="app-nav-drawer app-nav-drawer--open" aria-hidden={false}>
            <p className="app-nav-drawer__eyebrow">{cs.nav.mobilniNavigace}</p>
            <NavLinks
              className="app-nav app-nav--drawer flex-col items-stretch"
              onNavigate={() => setMenuOpen(false)}
            />
          </div>
        </>
      )}

      <div className="app-header__accent" aria-hidden />
    </header>
  );
}
