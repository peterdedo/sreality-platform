import { lazy, Suspense } from "react";
import { Route, Routes } from "react-router-dom";
import { NavBar } from "./components/layout/NavBar";
import { PageRouteFallback } from "./components/layout/PageRouteFallback";
import { PrehledTrhu } from "./pages/PrehledTrhu";
import { Nabidky } from "./pages/Nabidky";
import { DetailNabidky } from "./pages/DetailNabidky";
import { HistorieCen } from "./pages/HistorieCen";

const Mapa = lazy(() => import("./pages/Mapa").then((m) => ({ default: m.Mapa })));
const Analytika = lazy(() => import("./pages/Analytika").then((m) => ({ default: m.Analytika })));
const PokroziteAnalyzy = lazy(() =>
  import("./pages/PokroziteAnalyzy").then((m) => ({ default: m.PokroziteAnalyzy }))
);
const SpravaScrapingu = lazy(() =>
  import("./pages/SpravaScrapingu").then((m) => ({ default: m.SpravaScrapingu }))
);

export default function App() {
  return (
    <div className="min-h-screen bg-app-gradient app-canvas">
      <NavBar />
      <Suspense fallback={<PageRouteFallback />}>
        <Routes>
          <Route path="/" element={<PrehledTrhu />} />
          <Route path="/nabidky" element={<Nabidky />} />
          <Route path="/nabidky/:id" element={<DetailNabidky />} />
          <Route path="/mapa" element={<Mapa />} />
          <Route path="/analytika" element={<Analytika />} />
          <Route path="/historie-cen" element={<HistorieCen />} />
          <Route path="/pokrocile-analyzy" element={<PokroziteAnalyzy />} />
          <Route path="/sprava-scrapingu" element={<SpravaScrapingu />} />
        </Routes>
      </Suspense>
    </div>
  );
}
