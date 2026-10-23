import { lazy } from 'react'
import { Route, Routes } from 'react-router-dom'
import SiteLayout from './components/SiteLayout'
import LandingPage from './pages/LandingPage'

const ImagePage = lazy(() => import('./pages/ImagePage'))
const VideoPage = lazy(() => import('./pages/VideoPage'))
const CameraPage = lazy(() => import('./pages/CameraPage'))
const NotFoundPage = lazy(() => import('./pages/NotFoundPage'))

function App() {
  return (
    <Routes>
      <Route element={<SiteLayout />}>
        <Route index element={<LandingPage />} />
        <Route path="image" element={<ImagePage />} />
        <Route path="video" element={<VideoPage />} />
        <Route path="camera" element={<CameraPage />} />
        <Route path="*" element={<NotFoundPage />} />
      </Route>
    </Routes>
  )
}

export default App
