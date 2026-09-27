import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router'
import '@fontsource-variable/anek-latin/wdth.css'
import './styles.css'
import App from './App.jsx'
import { CompareProvider } from './compare.jsx'

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <BrowserRouter>
      <CompareProvider>
        <App />
      </CompareProvider>
    </BrowserRouter>
  </StrictMode>,
)
