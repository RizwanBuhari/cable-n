import { lazy, Suspense } from 'react'
import { Route, Routes } from 'react-router-dom'
import { AdProvider } from './components/Ads'
import AppLayout from './components/AppLayout'
import { CalcContextProvider } from './components/ChatPanel'
import { PageLoader } from './components/ui'
import HomePage from './pages/HomePage'

// Calculator and reference pages are split so the home page loads fast.
const CalculatorsPage = lazy(() => import('./pages/CalculatorsPage'))
const SingleFeederPage = lazy(() => import('./calculators/SingleFeederPage'))
const BatchPage = lazy(() => import('./calculators/BatchPage'))
const CurrentRatingPage = lazy(() => import('./calculators/CurrentRatingPage'))
const AdvancedPage = lazy(() => import('./calculators/AdvancedPage'))
const SavedCalculationPage = lazy(() => import('./pages/SavedCalculationPage'))
const LibraryPage = lazy(() => import('./pages/LibraryPage'))
const ComparisonPage = lazy(() => import('./pages/ComparisonPage'))
const ValidationPage = lazy(() => import('./pages/ValidationPage'))
const ResourcesPage = lazy(() => import('./pages/ResourcesPage'))
const SettingsPage = lazy(() => import('./pages/SettingsPage'))
const InfoPages = lazy(() => import('./pages/InfoPages'))

export default function App() {
  return (
    <AdProvider>
      <CalcContextProvider>
        <Suspense fallback={<PageLoader />}>
          <Routes>
            <Route element={<AppLayout />}>
              <Route path="/" element={<HomePage />} />
              <Route path="/calculators" element={<CalculatorsPage />} />
              <Route path="/calculators/single-feeder" element={<SingleFeederPage />} />
              <Route path="/calculators/batch" element={<BatchPage />} />
              <Route path="/calculators/current-rating" element={<CurrentRatingPage />} />
              <Route path="/calculators/advanced-mv-hv" element={<AdvancedPage />} />
              <Route path="/calculators/saved/:id" element={<SavedCalculationPage />} />
              <Route path="/cable-library" element={<LibraryPage />} />
              <Route path="/comparison" element={<ComparisonPage />} />
              <Route path="/validation" element={<ValidationPage />} />
              <Route path="/resources" element={<ResourcesPage />} />
              <Route path="/settings" element={<SettingsPage />} />
              <Route path="/about" element={<InfoPages page="about" />} />
              <Route path="/contact" element={<InfoPages page="contact" />} />
              <Route path="/privacy" element={<InfoPages page="privacy" />} />
              <Route path="/terms" element={<InfoPages page="terms" />} />
              <Route path="/disclaimer" element={<InfoPages page="disclaimer" />} />
              <Route path="*" element={<InfoPages page="notfound" />} />
            </Route>
          </Routes>
        </Suspense>
      </CalcContextProvider>
    </AdProvider>
  )
}
