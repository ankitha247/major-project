import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { login, register } from '../api/client'

export default function Login() {
  const navigate = useNavigate()
  const [isRegister, setIsRegister] = useState(false)
  const [form, setForm] = useState({
    email: '',
    password: '',
    full_name: '',
    role: 'investigator',
  })
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      const res = isRegister
        ? await register(form)
        : await login({ email: form.email, password: form.password })

      localStorage.setItem('token', res.data.access_token)
      localStorage.setItem('user', JSON.stringify({
        id: res.data.user_id,
        full_name: res.data.full_name,
        role: res.data.role,
      }))
      navigate('/dashboard')
    } catch (err) {
      setError(err.response?.data?.detail || 'Something went wrong')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div style={styles.container}>
      <div style={styles.card}>
        <h1 style={styles.title}>ForensicAI</h1>
        <p style={styles.subtitle}>AI-Powered Witness Interview Platform</p>

        <h2 style={styles.formTitle}>
          {isRegister ? 'Create Account' : 'Sign In'}
        </h2>

        <form onSubmit={handleSubmit}>
          {isRegister && (
            <input
              style={styles.input}
              placeholder='Full Name'
              value={form.full_name}
              onChange={(e) => setForm({ ...form, full_name: e.target.value })}
              required
            />
          )}
          <input
            style={styles.input}
            type='email'
            placeholder='Email'
            value={form.email}
            onChange={(e) => setForm({ ...form, email: e.target.value })}
            required
          />
          <input
            style={styles.input}
            type='password'
            placeholder='Password'
            value={form.password}
            onChange={(e) => setForm({ ...form, password: e.target.value })}
            required
          />

          {error && <p style={styles.error}>{error}</p>}

          <button style={styles.button} type='submit' disabled={loading}>
            {loading ? 'Please wait...' : isRegister ? 'Register' : 'Login'}
          </button>
        </form>

        <p style={styles.toggle}>
          {isRegister ? 'Already have an account?' : "Don't have an account?"}{' '}
          <span
            style={styles.link}
            onClick={() => setIsRegister(!isRegister)}
          >
            {isRegister ? 'Sign In' : 'Register'}
          </span>
        </p>
      </div>
    </div>
  )
}

const styles = {
  container: {
    minHeight: '100vh',
    background: '#0f0f1a',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    fontFamily: 'system-ui, sans-serif',
  },
  card: {
    background: '#1a1a2e',
    border: '1px solid #2a2a4a',
    borderRadius: 12,
    padding: '2.5rem',
    width: '100%',
    maxWidth: 420,
  },
  title: {
    color: '#7c6af7',
    fontSize: 28,
    fontWeight: 700,
    margin: 0,
    textAlign: 'center',
    letterSpacing: 2,
  },
  subtitle: {
    color: '#888',
    fontSize: 13,
    textAlign: 'center',
    marginTop: 6,
    marginBottom: 28,
  },
  formTitle: {
    color: '#fff',
    fontSize: 18,
    fontWeight: 600,
    marginBottom: 20,
  },
  input: {
    width: '100%',
    padding: '12px 14px',
    marginBottom: 14,
    background: '#0f0f1a',
    border: '1px solid #2a2a4a',
    borderRadius: 8,
    color: '#fff',
    fontSize: 14,
    boxSizing: 'border-box',
    outline: 'none',
  },
  button: {
    width: '100%',
    padding: '13px',
    background: '#7c6af7',
    color: '#fff',
    border: 'none',
    borderRadius: 8,
    fontSize: 15,
    fontWeight: 600,
    cursor: 'pointer',
    marginTop: 4,
  },
  error: {
    color: '#f87171',
    fontSize: 13,
    marginBottom: 12,
  },
  toggle: {
    color: '#888',
    fontSize: 13,
    textAlign: 'center',
    marginTop: 20,
  },
  link: {
    color: '#7c6af7',
    cursor: 'pointer',
    fontWeight: 600,
  },
}