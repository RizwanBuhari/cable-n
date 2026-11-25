import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import '@fontsource/montserrat/400.css'
import '@fontsource/montserrat/500.css'
import '@fontsource/montserrat/600.css'
import '@fontsource/montserrat/700.css'
import '@fontsource/montserrat/800.css'
import './styles/base.css'
import './styles/cablen.css'
import App from './App.jsx'
import { applyAccentColor, getStoredAccentId } from './lib/prefs'

// before first paint: no flash of the default red when another accent is saved
applyAccentColor(getStoredAccentId())

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <BrowserRouter>
      <App />
    </BrowserRouter>
  </StrictMode>,
)
