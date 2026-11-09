import { useState, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { analyzeFile, analyzeText } from '../api/client'

const CRIME_TYPES = [
  'Theft / Robbery', 'Assault / Battery', 'Hit and Run',
  'Burglary / Breaking & Entering', 'Vandalism / Property Damage',
  'Murder / Homicide', 'Kidnapping / Abduction', 'Sexual Assault',
  'Fraud / Cybercrime', 'Drug Offence', 'Arson', 'Other',
]

const ACCEPT = '.jpg,.jpeg,.png,.bmp,.webp,.mp4,.mov,.avi,.mkv,.webm'

export default function Upload() {
  const navigate = useNavigate()
  const fileRef = useRef(null)

  const [crimeType, setCrimeType] = useState('')
  const [witnessName, setWitnessName] = useState('')
  const [caseNumber, setCaseNumber] = useState('')
  const [file, setFile] = useState(null)
  const [preview, setPreview] = useState(null)
  const [loading, setLoading] = useState(false)
  const [loadingType, setLoadingType] = useState('')
  const [error, setError] = useState('')

  const validateBasics = () => {
    if (!crimeType) { setError('Please select a crime type'); return false }
    if (!witnessName.trim()) { setError('Please enter witness name'); return false }
    if (!caseNumber.trim()) { setError('Please enter case number'); return false }
    return true
  }

  const handleFileChange = (e) => {
    const f = e.target.files[0]
    if (!f) return
    setFile(f)
    setError('')
    const ext = f.name.split('.').pop().toLowerCase()
    const isVideo = ['mp4', 'mov', 'avi', 'mkv', 'webm'].includes(ext)
    setPreview({ url: URL.createObjectURL(f), type: isVideo ? 'video' : 'image' })
  }

  const handleAnalyzeWithEvidence = async () => {
    if (!validateBasics()) return
    if (!file) { setError('Please select a file or use Start Without Evidence below'); return }
    setLoading(true)
    setLoadingType('evidence')
    setError('')
    try {
      const res = await analyzeFile(file, crimeType)
      const { session_id, analysis, first_question } = res.data
      navigate(`/interview/${session_id}`, {
        state: { analysis, first_question, crime_type: crimeType, witness_name: witnessName, case_number: caseNumber }
      })
    } catch (err) {
      setError(err.response?.data?.detail || 'Analysis failed. Make sure the interview backend is running on port 8001.')
    } finally {
      setLoading(false)
      setLoadingType('')
    }
  }

  const handleStartWithoutEvidence = async () => {
    if (!validateBasics()) return
    setLoading(true)
    setLoadingType('direct')
    setError('')
    try {
      // Use a generic description so the backend creates a session
      const placeholder = `Witness interview for a ${crimeType} case. Witness name: ${witnessName}. Case number: ${caseNumber}. No physical evidence available at this time.`
      const res = await analyzeText(crimeType, placeholder)
      const { session_id, analysis, first_question } = res.data
      navigate(`/interview/${session_id}`, {
        state: { analysis, first_question, crime_type: crimeType, witness_name: witnessName, case_number: caseNumber }
      })
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to start interview. Make sure the interview backend is running on port 8001.')
    } finally {
      setLoading(false)
      setLoadingType('')
    }
  }

  return (
    <div style={styles.container}>
      <div style={styles.header}>
        <span style={styles.logo}>ForensicAI</span>
        <button style={styles.backBtn} onClick={() => navigate('/dashboard')}>
          ← Dashboard
        </button>
      </div>

      <div style={styles.card}>
        <h2 style={styles.title}>New Interview Session</h2>
        <p style={styles.subtitle}>
          Fill in the case details. Evidence upload is optional — you can start
          the interview directly without any CCTV footage or images.
        </p>

        {/* Case details */}
        <label style={styles.label}>Witness Name</label>
        <input
          style={styles.input}
          placeholder='Full name of the witness'
          value={witnessName}
          onChange={(e) => setWitnessName(e.target.value)}
        />

        <label style={styles.label}>Case Number</label>
        <input
          style={styles.input}
          placeholder='e.g. CASE-2024-001'
          value={caseNumber}
          onChange={(e) => setCaseNumber(e.target.value)}
        />

        <label style={styles.label}>Crime Type</label>
        <select
          style={styles.input}
          value={crimeType}
          onChange={(e) => setCrimeType(e.target.value)}
        >
          <option value=''>Select crime type</option>
          {CRIME_TYPES.map((t) => (
            <option key={t} value={t}>{t}</option>
          ))}
        </select>

        {/* Divider */}
        <div style={styles.divider}>
          <div style={styles.dividerLine} />
          <span style={styles.dividerText}>EVIDENCE (OPTIONAL)</span>
          <div style={styles.dividerLine} />
        </div>

        {/* File upload — optional */}
        <p style={styles.optionalNote}>
          Upload CCTV footage or crime scene photo if available.
          The AI will analyze it and use the findings during the interview.
        </p>

        <div
          style={{
            ...styles.dropZone,
            borderColor: file ? '#22c55e' : '#2a2a4a',
          }}
          onClick={() => fileRef.current?.click()}
        >
          {!file ? (
            <>
              <div style={{ fontSize: 36, marginBottom: 8 }}>📁</div>
              <p style={styles.dropText}>Click to select image or video</p>
              <p style={styles.dropSub}>JPG · PNG · MP4 · MOV · AVI · MKV · WEBM</p>
              <p style={styles.dropOptional}>Optional — leave empty to skip</p>
            </>
          ) : (
            <>
              <div style={{ fontSize: 28, marginBottom: 6 }}>✅</div>
              <p style={styles.fileName}>{file.name}</p>
              <p style={styles.fileSize}>{(file.size / 1024 / 1024).toFixed(1)} MB</p>
              <p
                style={styles.removeFile}
                onClick={(e) => {
                  e.stopPropagation()
                  setFile(null)
                  setPreview(null)
                }}
              >
                × Remove
              </p>
            </>
          )}
          <input
            ref={fileRef}
            type='file'
            accept={ACCEPT}
            style={{ display: 'none' }}
            onChange={handleFileChange}
          />
        </div>

        {/* Preview */}
        {preview?.type === 'image' && (
          <img src={preview.url} alt='preview' style={styles.preview} />
        )}
        {preview?.type === 'video' && (
          <video src={preview.url} controls style={styles.preview} />
        )}

        {error && <p style={styles.error}>{error}</p>}

        {/* Primary button — with evidence */}
        {file && (
          <button
            style={{ ...styles.primaryBtn, opacity: loading ? 0.7 : 1 }}
            onClick={handleAnalyzeWithEvidence}
            disabled={loading}
          >
            {loading && loadingType === 'evidence'
              ? preview?.type === 'video'
                ? '🎬 Analyzing video frames...'
                : '🔍 Analyzing image...'
              : '🔍 Analyze Evidence & Start Interview'}
          </button>
        )}

        {/* Always visible — start without evidence */}
        <button
          style={{
            ...styles.directBtn,
            opacity: loading ? 0.7 : 1,
            marginTop: file ? 10 : 20,
          }}
          onClick={handleStartWithoutEvidence}
          disabled={loading}
        >
          {loading && loadingType === 'direct'
            ? 'Starting interview...'
            : file
              ? 'Or Start Without Evidence'
              : '▶ Start Interview Without Evidence'}
        </button>

        <button
          style={styles.cancelBtn}
          onClick={() => navigate('/dashboard')}
          disabled={loading}
        >
          Cancel
        </button>
      </div>
    </div>
  )
}

const styles = {
  container: {
    minHeight: '100vh',
    background: '#0f0f1a',
    fontFamily: 'system-ui, sans-serif',
  },
  header: {
    background: '#1a1a2e',
    borderBottom: '1px solid #2a2a4a',
    padding: '1rem 2rem',
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  logo: { color: '#7c6af7', fontWeight: 700, fontSize: 20, letterSpacing: 2 },
  backBtn: {
    background: 'transparent',
    color: '#7c6af7',
    border: '1px solid #7c6af7',
    padding: '7px 16px',
    borderRadius: 8,
    cursor: 'pointer',
    fontSize: 13,
    fontWeight: 600,
  },
  card: {
    maxWidth: 580,
    margin: '2rem auto',
    background: '#1a1a2e',
    border: '1px solid #2a2a4a',
    borderRadius: 12,
    padding: '2rem',
  },
  title: { color: '#fff', fontSize: 22, fontWeight: 700, margin: '0 0 8px' },
  subtitle: { color: '#666', fontSize: 14, margin: '0 0 24px', lineHeight: 1.6 },
  label: {
    display: 'block',
    color: '#888',
    fontSize: 11,
    fontWeight: 700,
    textTransform: 'uppercase',
    letterSpacing: 0.5,
    marginBottom: 6,
    marginTop: 18,
  },
  input: {
    width: '100%',
    padding: '11px 14px',
    background: '#0f0f1a',
    border: '1px solid #2a2a4a',
    borderRadius: 8,
    color: '#fff',
    fontSize: 14,
    boxSizing: 'border-box',
    outline: 'none',
    fontFamily: 'system-ui, sans-serif',
  },
  divider: {
    display: 'flex',
    alignItems: 'center',
    gap: 12,
    margin: '24px 0 16px',
  },
  dividerLine: {
    flex: 1,
    height: 1,
    background: '#2a2a4a',
  },
  dividerText: {
    color: '#444',
    fontSize: 11,
    fontWeight: 700,
    letterSpacing: 1,
    whiteSpace: 'nowrap',
  },
  optionalNote: {
    color: '#555',
    fontSize: 13,
    margin: '0 0 14px',
    lineHeight: 1.5,
  },
  dropZone: {
    border: '2px dashed',
    borderRadius: 12,
    padding: '1.75rem',
    textAlign: 'center',
    cursor: 'pointer',
    marginBottom: 16,
    transition: 'border-color 0.2s',
  },
  dropText: { color: '#ccc', fontSize: 14, fontWeight: 600, margin: '0 0 4px' },
  dropSub: { color: '#444', fontSize: 12, margin: '0 0 4px' },
  dropOptional: { color: '#7c6af7', fontSize: 11, margin: 0, fontWeight: 600 },
  fileName: { color: '#22c55e', fontSize: 14, fontWeight: 600, margin: '0 0 2px' },
  fileSize: { color: '#555', fontSize: 12, margin: '0 0 6px' },
  removeFile: {
    color: '#ef4444',
    fontSize: 12,
    cursor: 'pointer',
    margin: 0,
    fontWeight: 600,
  },
  preview: {
    width: '100%',
    borderRadius: 8,
    marginBottom: 16,
    maxHeight: 220,
    objectFit: 'cover',
    display: 'block',
  },
  error: {
    color: '#f87171',
    fontSize: 13,
    margin: '8px 0',
    padding: '8px 12px',
    background: '#2a0a0a',
    borderRadius: 6,
    border: '1px solid #ef4444',
  },
  primaryBtn: {
    width: '100%',
    padding: '13px',
    background: '#7c6af7',
    color: '#fff',
    border: 'none',
    borderRadius: 8,
    fontSize: 15,
    fontWeight: 700,
    cursor: 'pointer',
    marginTop: 4,
  },
  directBtn: {
    width: '100%',
    padding: '13px',
    background: '#1a1a2e',
    color: '#7c6af7',
    border: '2px solid #7c6af7',
    borderRadius: 8,
    fontSize: 14,
    fontWeight: 700,
    cursor: 'pointer',
  },
  cancelBtn: {
    width: '100%',
    padding: '11px',
    background: 'transparent',
    color: '#444',
    border: '1px solid #2a2a4a',
    borderRadius: 8,
    fontSize: 13,
    cursor: 'pointer',
    marginTop: 10,
  },
}