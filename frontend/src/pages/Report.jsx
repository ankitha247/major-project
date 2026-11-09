import { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import {
  generateReport, downloadPDF, getSessionData,
  getCredibility, getCBCA,
} from '../api/client'

export default function Report() {
  const { sessionId } = useParams()
  const navigate      = useNavigate()

  const [report,      setReport]      = useState(null)
  const [session,     setSession]     = useState(null)
  const [credibility, setCredibility] = useState(null)
  const [summary,     setSummary]     = useState(null)
  const [cbca,        setCbca]        = useState(null)
  const [loading,     setLoading]     = useState(true)
  const [loadingCred, setLoadingCred] = useState(false)
  const [loadingCbca, setLoadingCbca] = useState(false)
  const [downloading, setDownloading] = useState(false)
  const [error,       setError]       = useState('')
  const [activeTab,   setActiveTab]   = useState('overview')

  useEffect(() => { loadReport() }, [sessionId])

  const loadReport = async () => {
    try {
      const [repRes, sessRes] = await Promise.all([
        generateReport(sessionId),
        getSessionData(sessionId),
      ])
      setReport(repRes.data.report)
      setSession(sessRes.data)
    } catch (err) {
      setError('Failed to load report')
    } finally {
      setLoading(false)
    }
  }

  const loadCredibility = async () => {
    setLoadingCred(true)
    try {
      const res = await getCredibility(sessionId)
      setCredibility(res.data.credibility)
      setSummary(res.data.case_summary)
      setActiveTab('credibility')
    } catch (err) {
      setError('Failed to generate analysis')
    } finally {
      setLoadingCred(false)
    }
  }

  const loadCbca = async () => {
    setLoadingCbca(true)
    try {
      const res = await getCBCA(sessionId)
      setCbca(res.data.cbca)
      setActiveTab('cbca')
    } catch (err) {
      setError('Failed to generate CBCA score')
    } finally {
      setLoadingCbca(false)
    }
  }

  const handleDownloadPDF = async () => {
    setDownloading(true)
    try {
      const res  = await downloadPDF(sessionId)
      const url  = window.URL.createObjectURL(new Blob([res.data]))
      const link = document.createElement('a')
      link.href  = url
      link.setAttribute('download', `report_${sessionId}.pdf`)
      document.body.appendChild(link)
      link.click()
      link.remove()
      window.URL.revokeObjectURL(url)
    } catch {
      alert('PDF generation failed')
    } finally {
      setDownloading(false)
    }
  }

  const handleDownloadTXT = () => {
    if (!report) return
    const blob = new Blob([report], { type: 'text/plain' })
    const url  = window.URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href  = url
    link.setAttribute('download', `report_${sessionId}.txt`)
    document.body.appendChild(link)
    link.click()
    link.remove()
    window.URL.revokeObjectURL(url)
  }

  const renderMarkdown = (text) => {
    if (!text) return null
    return text.split('\n').map((line, i) => {
      if (line.startsWith('## ')) return <h3 key={i} style={styles.reportH2}>{line.slice(3)}</h3>
      if (line.startsWith('# '))  return <h2 key={i} style={styles.reportH1}>{line.slice(2)}</h2>
      if (line.startsWith('- ') || line.startsWith('* '))
        return <p key={i} style={styles.reportBullet}>• {line.slice(2)}</p>
      if (!line.trim()) return <br key={i} />
      return <p key={i} style={styles.reportPara}>{line}</p>
    })
  }

  const scoreColor = (pct) =>
    pct >= 70 ? '#22c55e' : pct >= 45 ? '#f59e0b' : '#ef4444'

  const msgCount = session?.conversation?.length || 0
  const qCount   = Math.ceil(msgCount / 2)

  if (loading) return (
    <div style={styles.center}><p style={{ color: '#888' }}>Generating report...</p></div>
  )
  if (error) return (
    <div style={styles.center}><p style={{ color: '#ef4444' }}>{error}</p></div>
  )

  return (
    <div style={styles.container}>

      {/* Header */}
      <div style={styles.header}>
        <button style={styles.backBtn} onClick={() => navigate('/dashboard')}>
          ← Dashboard
        </button>
        <h1 style={styles.logo}>ForensicAI — Session Report</h1>
        <div style={styles.downloadRow}>
          <button style={styles.txtBtn} onClick={handleDownloadTXT}>⬇ TXT</button>
          <button
            style={{ ...styles.pdfBtn, opacity: downloading ? 0.6 : 1 }}
            onClick={handleDownloadPDF}
            disabled={downloading}
          >
            {downloading ? 'Generating...' : '⬇ PDF'}
          </button>
        </div>
      </div>

      {/* Tabs */}
      <div style={styles.tabs}>
        {[
          { key: 'overview',     label: 'Overview' },
          { key: 'report',       label: 'Full Report' },
          { key: 'credibility',  label: '📊 Case Summary' },
          { key: 'cbca',         label: '🧠 CBCA Analysis' },
        ].map((tab) => (
          <button
            key={tab.key}
            style={{
              ...styles.tab,
              borderBottom: activeTab === tab.key ? '2px solid #7c6af7' : '2px solid transparent',
              color:        activeTab === tab.key ? '#fff' : '#666',
            }}
            onClick={() => {
              if (tab.key === 'credibility' && !credibility) loadCredibility()
              else if (tab.key === 'cbca' && !cbca) loadCbca()
              else setActiveTab(tab.key)
            }}
          >
            {tab.key === 'credibility' && loadingCred ? 'Analyzing...' :
             tab.key === 'cbca' && loadingCbca ? 'Scoring...' : tab.label}
          </button>
        ))}
      </div>

      <div style={styles.main}>

        {/* Overview */}
        {activeTab === 'overview' && (
          <>
            <div style={styles.card}>
              <h2 style={styles.cardTitle}>Session Overview</h2>
              <div style={styles.metricsRow}>
                <div style={styles.metric}>
                  <span style={styles.metricValue}>{sessionId}</span>
                  <span style={styles.metricLabel}>Session ID</span>
                </div>
                <div style={styles.metric}>
                  <span style={styles.metricValue}>{session?.crime_type || '—'}</span>
                  <span style={styles.metricLabel}>Crime Type</span>
                </div>
                <div style={styles.metric}>
                  <span style={styles.metricValue}>{qCount}</span>
                  <span style={styles.metricLabel}>Questions Asked</span>
                </div>
                <div style={styles.metric}>
                  <span style={{
                    ...styles.metricValue,
                    color: session?.status === 'completed' ? '#22c55e' : '#f59e0b',
                  }}>
                    {session?.status?.toUpperCase() || '—'}
                  </span>
                  <span style={styles.metricLabel}>Status</span>
                </div>
              </div>
            </div>

            <div style={styles.card}>
              <h2 style={styles.cardTitle}>Analysis Tools</h2>
              <div style={styles.actionRow}>
                <button
                  style={styles.actionBtn}
                  onClick={() => credibility ? setActiveTab('credibility') : loadCredibility()}
                  disabled={loadingCred}
                >
                  📊 {loadingCred ? 'Generating...' : 'Case Summary & Analysis'}
                </button>
                <button
                  style={styles.actionBtnSecondary}
                  onClick={() => cbca ? setActiveTab('cbca') : loadCbca()}
                  disabled={loadingCbca}
                >
                  🧠 {loadingCbca ? 'Scoring...' : 'CBCA Content Analysis'}
                </button>
              </div>
              <p style={styles.disclaimer}>
                ⚠ All AI-generated scores are research tools only and must not be used as
                evidence of truthfulness or deception in legal proceedings.
              </p>
            </div>
          </>
        )}

        {/* Full Report */}
        {activeTab === 'report' && (
          <div style={styles.card}>
            <h2 style={styles.cardTitle}>Investigation Report</h2>
            <div style={styles.reportText}>{renderMarkdown(report)}</div>
          </div>
        )}

        {/* Case Summary */}
        {activeTab === 'credibility' && credibility && (
          <>
            <div style={styles.card}>
              <h2 style={styles.cardTitle}>Session Statistics</h2>
              <div style={styles.statsRow}>
                <div style={styles.statItem}>
                  <span style={styles.statValue}>{credibility.total_responses}</span>
                  <span style={styles.statLabel}>Total Responses</span>
                </div>
                <div style={styles.statItem}>
                  <span style={styles.statValue}>{credibility.avg_response_words}</span>
                  <span style={styles.statLabel}>Avg Words/Response</span>
                </div>
                <div style={styles.statItem}>
                  <span style={{
                    ...styles.statValue,
                    color: credibility.contradiction_count > 0 ? '#ef4444' : '#22c55e',
                  }}>
                    {credibility.contradiction_count}
                  </span>
                  <span style={styles.statLabel}>Contradictions</span>
                </div>
              </div>
            </div>

            {summary && (
              <div style={styles.card}>
                <h2 style={styles.cardTitle}>Automatic Case Summary</h2>
                <div style={styles.reportText}>{renderMarkdown(summary)}</div>
              </div>
            )}
          </>
        )}

        {/* CBCA Analysis */}
        {activeTab === 'cbca' && cbca && (
          <>
            {/* Score header */}
            <div style={styles.card}>
              <h2 style={styles.cardTitle}>CBCA-Inspired Content Analysis Score</h2>
              <p style={styles.cbcaMethod}>{cbca.method}</p>

              <div style={styles.cbcaScoreRow}>
                <div style={styles.cbcaScoreCircle}>
                  <span style={{ ...styles.cbcaBig, color: scoreColor(cbca.percentage) }}>
                    {cbca.total_score}
                  </span>
                  <span style={styles.cbcaMax}>/ {cbca.max_score}</span>
                  <span style={{
                    ...styles.cbcaGrade,
                    color: scoreColor(cbca.percentage),
                  }}>
                    {cbca.interpretation} ({cbca.percentage}%)
                  </span>
                </div>
                <div style={styles.cbcaInterpBox}>
                  <p style={styles.cbcaInterpText}>{cbca.interpretation_text}</p>
                  <p style={styles.cbcaDisclaimer}>{cbca.disclaimer}</p>
                </div>
              </div>
            </div>

            {/* Category breakdown */}
            <div style={styles.card}>
              <h2 style={styles.cardTitle}>Score by Category</h2>
              {Object.entries(cbca.category_scores || {}).map(([cat, data]) => {
                const pct = (data.score / data.max) * 100
                return (
                  <div key={cat} style={styles.catRow}>
                    <span style={styles.catLabel}>{cat}</span>
                    <div style={styles.catTrack}>
                      <div style={{
                        ...styles.catFill,
                        width:      `${pct}%`,
                        background: scoreColor(pct),
                      }} />
                    </div>
                    <span style={styles.catScore}>{data.score}/{data.max}</span>
                  </div>
                )
              })}
            </div>

            {/* Detailed criteria */}
            <div style={styles.card}>
              <h2 style={styles.cardTitle}>Detailed Criteria Evaluation</h2>
              {['General Characteristics', 'Specific Contents',
                'Peculiarities of Content', 'Offence-Specific Elements'].map((cat) => (
                <div key={cat} style={styles.cbcaCategory}>
                  <h3 style={styles.cbcaCatTitle}>{cat}</h3>
                  {(cbca.breakdown || [])
                    .filter((c) => c.category === cat)
                    .map((c) => (
                      <div key={c.id} style={styles.cbcaItem}>
                        <div style={styles.cbcaItemHeader}>
                          <span style={{
                            ...styles.cbcaBadge,
                            background: c.score === 1 ? '#22c55e22' : '#ef444422',
                            color:      c.score === 1 ? '#22c55e' : '#ef4444',
                            border:     `1px solid ${c.score === 1 ? '#22c55e' : '#ef4444'}`,
                          }}>
                            {c.score === 1 ? '✓ PRESENT' : '✗ ABSENT'}
                          </span>
                          <span style={styles.cbcaName}>
                            {c.id}. {c.name}
                          </span>
                        </div>
                        {c.reasoning && (
                          <p style={styles.cbcaReasoning}>{c.reasoning}</p>
                        )}
                      </div>
                    ))}
                </div>
              ))}
            </div>
          </>
        )}

        {activeTab === 'cbca' && !cbca && !loadingCbca && (
          <div style={styles.card}>
            <p style={{ color: '#666', textAlign: 'center', padding: '2rem' }}>
              Click "CBCA Analysis" tab to generate the content analysis score.
            </p>
          </div>
        )}

        {activeTab === 'credibility' && !credibility && !loadingCred && (
          <div style={styles.card}>
            <p style={{ color: '#666', textAlign: 'center', padding: '2rem' }}>
              Click "Case Summary" tab to generate analysis.
            </p>
          </div>
        )}

      </div>
    </div>
  )
}

const styles = {
  container:       { minHeight: '100vh', background: '#0f0f1a', fontFamily: 'system-ui, sans-serif' },
  center:          { minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center', background: '#0f0f1a' },
  header:          { background: '#1a1a2e', borderBottom: '1px solid #2a2a4a', padding: '1rem 2rem', display: 'flex', justifyContent: 'space-between', alignItems: 'center' },
  backBtn:         { background: 'transparent', color: '#7c6af7', border: '1px solid #7c6af7', padding: '7px 16px', borderRadius: 8, cursor: 'pointer', fontSize: 13, fontWeight: 600 },
  logo:            { color: '#fff', fontSize: 18, fontWeight: 600, margin: 0 },
  downloadRow:     { display: 'flex', gap: 10 },
  txtBtn:          { background: 'transparent', color: '#888', border: '1px solid #444', padding: '7px 16px', borderRadius: 8, cursor: 'pointer', fontSize: 13, fontWeight: 600 },
  pdfBtn:          { background: '#7c6af7', color: '#fff', border: 'none', padding: '7px 20px', borderRadius: 8, cursor: 'pointer', fontSize: 13, fontWeight: 700 },
  tabs:            { background: '#1a1a2e', borderBottom: '1px solid #2a2a4a', display: 'flex', padding: '0 2rem', overflowX: 'auto' },
  tab:             { background: 'transparent', border: 'none', padding: '1rem 1.25rem', cursor: 'pointer', fontSize: 13, fontWeight: 600, transition: 'color 0.2s', whiteSpace: 'nowrap' },
  main:            { maxWidth: 960, margin: '0 auto', padding: '2rem' },
  card:            { background: '#1a1a2e', border: '1px solid #2a2a4a', borderRadius: 12, padding: '1.5rem', marginBottom: 20 },
  cardTitle:       { color: '#7c6af7', fontSize: 15, fontWeight: 600, margin: '0 0 16px' },
  metricsRow:      { display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 12 },
  metric:          { background: '#0f0f1a', border: '1px solid #2a2a4a', borderRadius: 10, padding: '1rem', textAlign: 'center' },
  metricValue:     { display: 'block', fontSize: 18, fontWeight: 700, color: '#fff', marginBottom: 6, wordBreak: 'break-all' },
  metricLabel:     { color: '#666', fontSize: 11, textTransform: 'uppercase', letterSpacing: 0.5 },
  actionRow:       { display: 'flex', gap: 12, flexWrap: 'wrap', marginBottom: 16 },
  actionBtn:       { flex: 1, padding: '13px 20px', background: '#7c6af7', color: '#fff', border: 'none', borderRadius: 8, cursor: 'pointer', fontSize: 14, fontWeight: 700 },
  actionBtnSecondary: { flex: 1, padding: '13px 20px', background: 'transparent', color: '#7c6af7', border: '2px solid #7c6af7', borderRadius: 8, cursor: 'pointer', fontSize: 14, fontWeight: 600 },
  disclaimer:      { color: '#555', fontSize: 12, margin: 0, padding: '8px 12px', background: '#0f0f1a', borderRadius: 6, border: '1px solid #2a2a4a', lineHeight: 1.5 },
  statsRow:        { display: 'flex', gap: 16 },
  statItem:        { flex: 1, textAlign: 'center', background: '#0f0f1a', border: '1px solid #2a2a4a', borderRadius: 8, padding: '1rem' },
  statValue:       { display: 'block', fontSize: 22, fontWeight: 700, color: '#fff', marginBottom: 4 },
  statLabel:       { color: '#666', fontSize: 11, textTransform: 'uppercase', letterSpacing: 0.5 },
  reportText:      { color: '#ccc' },
  reportH1:        { color: '#fff', fontSize: 18, fontWeight: 700, margin: '20px 0 8px' },
  reportH2:        { color: '#7c6af7', fontSize: 15, fontWeight: 700, margin: '16px 0 6px', borderBottom: '1px solid #2a2a4a', paddingBottom: 6 },
  reportBullet:    { color: '#ccc', fontSize: 14, margin: '4px 0', paddingLeft: 8, lineHeight: 1.6 },
  reportPara:      { color: '#ccc', fontSize: 14, margin: '4px 0', lineHeight: 1.7 },
  cbcaMethod:      { color: '#555', fontSize: 12, margin: '0 0 16px', fontStyle: 'italic' },
  cbcaScoreRow:    { display: 'flex', gap: 24, alignItems: 'flex-start', flexWrap: 'wrap' },
  cbcaScoreCircle: { display: 'flex', flexDirection: 'column', alignItems: 'center', background: '#0f0f1a', border: '1px solid #2a2a4a', borderRadius: 12, padding: '1.5rem 2rem', minWidth: 140 },
  cbcaBig:         { fontSize: 52, fontWeight: 800, lineHeight: 1 },
  cbcaMax:         { color: '#555', fontSize: 15, marginTop: 2 },
  cbcaGrade:       { fontSize: 13, fontWeight: 700, marginTop: 8, letterSpacing: 0.5, textAlign: 'center' },
  cbcaInterpBox:   { flex: 1, minWidth: 200 },
  cbcaInterpText:  { color: '#ccc', fontSize: 14, lineHeight: 1.6, margin: '0 0 12px' },
  cbcaDisclaimer:  { color: '#555', fontSize: 11, lineHeight: 1.5, margin: 0, fontStyle: 'italic' },
  catRow:          { display: 'flex', alignItems: 'center', gap: 12, marginBottom: 10 },
  catLabel:        { color: '#888', fontSize: 12, width: 200, flexShrink: 0 },
  catTrack:        { flex: 1, height: 8, background: '#2a2a4a', borderRadius: 4, overflow: 'hidden' },
  catFill:         { height: '100%', borderRadius: 4, transition: 'width 0.5s' },
  catScore:        { color: '#666', fontSize: 11, width: 36, textAlign: 'right' },
  cbcaCategory:    { marginBottom: 20 },
  cbcaCatTitle:    { color: '#7c6af7', fontSize: 13, fontWeight: 700, margin: '0 0 10px', paddingBottom: 6, borderBottom: '1px solid #2a2a4a' },
  cbcaItem:        { background: '#0f0f1a', borderRadius: 8, padding: '10px 12px', marginBottom: 8 },
  cbcaItemHeader:  { display: 'flex', alignItems: 'center', gap: 10, marginBottom: 4 },
  cbcaBadge:       { fontSize: 10, fontWeight: 700, padding: '2px 8px', borderRadius: 4, flexShrink: 0 },
  cbcaName:        { color: '#ccc', fontSize: 13, fontWeight: 600 },
  cbcaReasoning:   { color: '#666', fontSize: 12, margin: 0, lineHeight: 1.5, paddingLeft: 4 },
}