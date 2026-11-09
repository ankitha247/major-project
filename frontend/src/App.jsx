import { Routes, Route, Navigate } from 'react-router-dom'
import Login from './pages/Login'
import Dashboard from './pages/Dashboard'
import Upload from './pages/Upload'
import Interview from './pages/Interview'
import Report from './pages/Report'

const Protected = ({ children }) => {
  const token = localStorage.getItem('token')
  return token ? children : <Navigate to='/' />
}

function App() {
  return (
    <Routes>
      <Route path='/' element={<Login />} />
      <Route path='/dashboard' element={<Protected><Dashboard /></Protected>} />
      <Route path='/upload' element={<Protected><Upload /></Protected>} />
      <Route path='/interview/:sessionId' element={<Protected><Interview /></Protected>} />
      <Route path='/report/:sessionId' element={<Protected><Report /></Protected>} />
    </Routes>
  )
}

export default App