import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { App } from 'components/App'
import './index.css'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <div className="min-h-screen bg-base">
      <App />
    </div>
  </StrictMode>
)
