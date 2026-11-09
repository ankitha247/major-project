import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { getAllSessions, deleteInterviewSession } from '../api/client'

export default function Dashboard() {
  const navigate = useNavigate()
  const user = JSON.parse(localStorage.getItem('user') || '{}')
  const [sessions, setSessions] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => { fetchSessions() }, [])

  const fetchSessions = async () => {
    try {
      const res = await getAllSessions()
      setSessions(res.data.sessions || [])
    } catch (err) {
      console.error('Failed to load sessions', err)
    } finally {
      setLoading(false)
    }
  }

  const handleDelete = async (id) => {
    if (!window.confirm('Delete this session?')) return
    try {
      await deleteInterviewSession(id)
      setSessions((prev) => prev.filter((s) => s.id !== id))
    } catch {
      alert('Delete failed')
    }
  }

  const handleLogout = () => {
    localStorage.clear()
    navigate('/')
  }

  const statusColor = (status) =>
    status === 'completed' ? '#22c55e'
    : status === 'active' ? '#7c6af7'
    : '#888'

  return (
    <div style={styles.container}>
      <div style={styles.header}>
        <h1 style={styles.logo}>ForensicAI</h1>
        <div style={styles.headerRight}>
          <span style={styles.userName}>{user.full_name}</span>
          <button style={styles.newBtn} onClick={() => navigate('/upload')}>
            + New Session
          </button>
          <button style={styles.logoutBtn} onClick={handleLogout}>
            Logout
          </button>
        </div>
      </div>

      <div style={styles.main}>
        <h2 style={styles.pageTitle}>Interview Sessions</h2>

        {loading && <p style={{ color: '#666' }}>Loading...</p>}

        {!loading && sessions.length === 0 && (
          <div style={styles.empty}>
            <p>No sessions yet. Click + New Session to begin.</p>
          </div>
        )}

        <div style={styles.grid}>
          {sessions.map((s) => (
            <div key={s.id} style={styles.card}>
              <div style={styles.cardHeader}>
                <span style={styles.sessionId}>{s.id}</span>
                <span style={{
                  ...styles.badge,
                  color: statusColor(s.status),
                  borderColor: statusColor(s.status),
                }}>
                  {s.status}
                </span>
              </div>
              <p style={styles.crimeType}>{s.crime_type}</p>
              <p style={styles.date}>
                {new Date(s.created_at).toLocaleString()}
              </p>
              <div style={styles.actions}>
                <button
                  style={styles.reportBtn}
                  onClick={() => navigate(`/report/${s.id}`)}
                >
                  View Report
                </button>
                <button
                  style={styles.deleteBtn}
                  onClick={() => handleDelete(s.id)}
                >
                  🗑
                </button>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

const styles = {
  container: { minHeight: '100vh', background: '#0f0f1a', fontFamily: 'system-ui, sans-serif' },
  header: { background: '#1a1a2e', borderBottom: '1px solid #2a2a4a', padding: '1rem 2rem', display: 'flex', justifyContent: 'space-between', alignItems: 'center' },
  logo: { color: '#7c6af7', fontSize: 22, fontWeight: 700, margin: 0, letterSpacing: 2 },
  headerRight: { display: 'flex', alignItems: 'center', gap: 12 },
  userName: { color: '#ccc', fontSize: 14 },
  newBtn: { background: '#7c6af7', color: '#fff', border: 'none', padding: '10px 20px', borderRadius: 8, cursor: 'pointer', fontSize: 14, fontWeight: 600 },
  logoutBtn: { background: 'transparent', border: '1px solid #444', color: '#ccc', padding: '8px 16px', borderRadius: 8, cursor: 'pointer', fontSize: 13 },
  main: { maxWidth: 1100, margin: '0 auto', padding: '2rem' },
  pageTitle: { color: '#fff', fontSize: 22, fontWeight: 600, marginBottom: 24 },
  empty: { textAlign: 'center', color: '#666', padding: '4rem', background: '#1a1a2e', borderRadius: 12, border: '1px solid #2a2a4a' },
  grid: { display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(300px, 1fr))', gap: 16 },
  card: { background: '#1a1a2e', border: '1px solid #2a2a4a', borderRadius: 12, padding: '1.25rem' },
  cardHeader: { display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 },
  sessionId: { color: '#7c6af7', fontSize: 13, fontWeight: 700 },
  badge: { fontSize: 11, fontWeight: 600, border: '1px solid', padding: '2px 8px', borderRadius: 20, textTransform: 'uppercase' },
  crimeType: { color: '#fff', fontSize: 15, fontWeight: 600, margin: '0 0 4px' },
  date: { color: '#555', fontSize: 12, margin: '0 0 14px' },
  actions: { display: 'flex', gap: 10 },
  reportBtn: { flex: 1, background: '#7c6af7', color: '#fff', border: 'none', padding: '9px', borderRadius: 8, cursor: 'pointer', fontSize: 13, fontWeight: 600 },
  deleteBtn: { background: 'transparent', color: '#666', border: '1px solid #2a2a4a', padding: '9px 14px', borderRadius: 8, cursor: 'pointer', fontSize: 13 },
}