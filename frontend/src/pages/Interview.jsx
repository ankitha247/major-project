import { useState, useEffect, useRef } from 'react'
import { useParams, useNavigate, useLocation } from 'react-router-dom'
import { respondToQuestion, analyzeEmotionFrame } from '../api/client'

const PHASES = [
  { key: 'rapport',       label: 'Rapport',       color: '#7c6af7' },
  { key: 'free_recall',   label: 'Free Recall',   color: '#06b6d4' },
  { key: 'probing',       label: 'Probing',       color: '#f59e0b' },
  { key: 'clarification', label: 'Clarification', color: '#ec4899' },
  { key: 'closure',       label: 'Closure',       color: '#22c55e' },
]

const EMOTION_COLORS = {
  happy: '#22c55e', neutral: '#7c6af7', sad: '#3b82f6',
  angry: '#ef4444', fear: '#f59e0b', disgust: '#a855f7',
  surprise: '#06b6d4', none: '#444',
}

const EMOTION_EMOJI = {
  happy: '😊', neutral: '😐', sad: '😢', angry: '😠',
  fear: '😨', disgust: '🤢', surprise: '😲', none: '👤',
}

export default function Interview() {
  const { sessionId } = useParams()
  const navigate      = useNavigate()
  const location      = useLocation()

  const { analysis, first_question, crime_type } = location.state || {}

  const [messages,            setMessages]            = useState(
    first_question ? [{
      role: 'assistant', content: first_question,
      timestamp: new Date().toLocaleTimeString(),
    }] : []
  )
  const [input,               setInput]               = useState('')
  const [sending,             setSending]             = useState(false)
  const [complete,            setComplete]            = useState(false)
  const [phase,               setPhase]               = useState('rapport')
  const [contradictions,      setContradictions]      = useState([])
  const [deceptionIndicators, setDeceptionIndicators] = useState([])
  const [emotion,             setEmotion]             = useState('none')
  const [stressLevel,         setStressLevel]         = useState(0)
  const [faceDetected,        setFaceDetected]        = useState(false)
  const [stressHistory,       setStressHistory]       = useState([])
  const [listening,           setListening]           = useState(false)
  const [language,            setLanguage]            = useState('en-IN')

  const chatEndRef    = useRef(null)
  const webcamRef     = useRef(null)
  const streamRef     = useRef(null)
  const frameCountRef = useRef(0)
  const intervalRef   = useRef(null)
  const recognitionRef = useRef(null)

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  useEffect(() => {
    startWebcam()
    return () => {
      streamRef.current?.getTracks().forEach((t) => t.stop())
      if (intervalRef.current) clearInterval(intervalRef.current)
      recognitionRef.current?.stop()
    }
  }, [])

  const startWebcam = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ video: true })
      streamRef.current = stream
      if (webcamRef.current) webcamRef.current.srcObject = stream
      intervalRef.current = setInterval(captureAndAnalyzeFrame, 1000)
    } catch (err) {
      console.warn('Webcam not available')
    }
  }

 const currentQuestionRef = useRef('')

// Update this ref whenever a new AI question arrives
// Add this inside handleServerMessage or inside the messages state update:
// currentQuestionRef.current = data.next_question

const captureAndAnalyzeFrame = async () => {
  if (!webcamRef.current || !streamRef.current) return
  try {
    const canvas = document.createElement('canvas')
    canvas.width  = 480
    canvas.height = 360
    canvas.getContext('2d').drawImage(webcamRef.current, 0, 0, 480, 360)
    const base64 = canvas.toDataURL('image/jpeg', 0.8).split(',')[1]
    const res    = await analyzeEmotionFrame(
      base64,
      frameCountRef.current++,
      currentQuestionRef.current,  // pass current question as context
    )
    const data = res.data
    setFaceDetected(data.face_detected)
    if (data.face_detected) {
      setEmotion(data.dominant_emotion)
      setStressLevel(data.stress_indicator)
      setStressHistory((prev) => [...prev, {
        stress:    data.stress_indicator,
        emotion:   data.dominant_emotion,
        scores:    data.emotion_scores,
        timestamp: data.timestamp,
        question:  data.question_context,
      }].slice(-60))  // keep last 60 readings = 1 minute at 1fps
    }
  } catch (err) {}
}

  const toggleListening = () => {
    const SpeechRecognition =
      window.SpeechRecognition || window.webkitSpeechRecognition

    if (!SpeechRecognition) {
      alert('Voice input is not supported in this browser. Please use Chrome or Edge.')
      return
    }

    if (listening) {
      recognitionRef.current?.stop()
      setListening(false)
      return
    }

    const recognition          = new SpeechRecognition()
    recognition.lang           = language
    recognition.continuous     = false
    recognition.interimResults = true

    recognition.onstart = () => setListening(true)

    recognition.onresult = (event) => {
      let transcript = ''
      for (let i = event.resultIndex; i < event.results.length; i++) {
        transcript += event.results[i][0].transcript
      }
      setInput(transcript)
    }

    recognition.onerror = (event) => {
      console.warn('Speech error:', event.error)
      setListening(false)
      if (event.error === 'network') {
        alert('Voice input failed — network error. Please type instead.')
      }
    }

    recognition.onend = () => setListening(false)

    recognitionRef.current = recognition
    recognition.start()
  }

  const sendResponse = async () => {
    if (!input.trim() || sending || complete) return
    const answer   = input.trim()
    const sendTime = new Date().toLocaleTimeString()
    setInput('')
    setSending(true)
    if (listening) {
      recognitionRef.current?.stop()
      setListening(false)
    }

    setMessages((prev) => [...prev, {
      role: 'user', content: answer, timestamp: sendTime,
    }])

    try {
      const res  = await respondToQuestion(sessionId, answer)
      const data = res.data

      if (data.phase) setPhase(data.phase)
      if (data.contradictions?.length > 0)
        setContradictions((prev) => [...prev, ...data.contradictions])
      if (data.deception_indicators?.length > 0)
        setDeceptionIndicators((prev) => [...prev, ...data.deception_indicators])

      if (data.complete) {
        setComplete(true)
        setMessages((prev) => [...prev, { role: 'system', content: 'Interview complete.' }])
      } else {
        setMessages((prev) => [...prev, {
          role: 'assistant', content: data.next_question,
          timestamp: new Date().toLocaleTimeString(),
        }])
      }
    } catch (err) {
      setMessages((prev) => [...prev, {
        role: 'assistant', content: '⚠ Connection error — please try again.',
      }])
    } finally {
      setSending(false)
    }
  }

  const currentPhaseIndex = PHASES.findIndex((p) => p.key === phase)
  const stressColor = stressLevel >= 0.75 ? '#ef4444' : stressLevel >= 0.4 ? '#f59e0b' : '#22c55e'
  const stressLabel = stressLevel >= 0.75 ? 'HIGH' : stressLevel >= 0.4 ? 'MODERATE' : 'LOW'
  const avgStress   = stressHistory.length > 0
    ? stressHistory.reduce((a, b) => a + b, 0) / stressHistory.length : 0
  const totalFlags  = contradictions.length + deceptionIndicators.length

  return (
    <div style={styles.root}>

      {/* ── Header ── */}
      <div style={styles.header}>
        <div style={styles.headerLeft}>
          <span style={styles.logo}>ForensicAI</span>
          <span style={styles.caseInfo}>{crime_type} · {sessionId}</span>
        </div>
        <div style={styles.headerRight}>
          {faceDetected && (
            <div style={styles.headerStress}>
              <span style={styles.headerStressLabel}>Stress</span>
              <div style={styles.headerStressBar}>
                <div style={{
                  ...styles.headerStressFill,
                  width: `${stressLevel * 100}%`,
                  background: stressColor,
                }} />
              </div>
              <span style={{ color: stressColor, fontSize: 11, fontWeight: 700 }}>
                {stressLabel}
              </span>
            </div>
          )}
          {totalFlags > 0 && (
            <div style={styles.flagBadge}>
              ⚠ {totalFlags} Flag{totalFlags > 1 ? 's' : ''}
            </div>
          )}
          {!complete && (
            <button style={styles.endBtn} onClick={() => setComplete(true)}>End</button>
          )}
          <button style={styles.reportBtn} onClick={() => navigate(`/report/${sessionId}`)}>
            Report
          </button>
        </div>
      </div>

      {/* ── Phase indicator bar ── */}
      <div style={styles.phaseBar}>
        {PHASES.map((p, i) => (
          <div key={p.key} style={styles.phaseItem}>
            <div style={{
              ...styles.phaseDot,
              background:  i < currentPhaseIndex ? '#22c55e' : i === currentPhaseIndex ? p.color : '#2a2a4a',
              borderColor: i <= currentPhaseIndex ? (i < currentPhaseIndex ? '#22c55e' : p.color) : '#2a2a4a',
            }}>
              {i < currentPhaseIndex ? '✓' : i + 1}
            </div>
            <span style={{
              ...styles.phaseLabel,
              color: i === currentPhaseIndex ? p.color : i < currentPhaseIndex ? '#22c55e' : '#444',
            }}>
              {p.label}
            </span>
            {i < PHASES.length - 1 && (
              <div style={{
                ...styles.phaseLine,
                background: i < currentPhaseIndex ? '#22c55e' : '#2a2a4a',
              }} />
            )}
          </div>
        ))}
      </div>

      {/* ── Body ── */}
      <div style={styles.body}>

        {/* Left panel */}
        <div style={styles.left}>
          <div style={styles.camBox}>
            <video ref={webcamRef} autoPlay muted playsInline style={styles.cam} />
            <span style={styles.camLabel}>Live Feed</span>
          </div>

          <div style={styles.leftScroll}>

            {/* Emotion */}
            <div style={styles.section}>
              <p style={styles.sectionTitle}>LIVE EMOTION</p>
              {!faceDetected && stressHistory.length === 0 ? (
                <p style={styles.dimText}>Waiting for face...</p>
              ) : (
                <>
                  <div style={styles.emotionRow}>
                    <span style={{ fontSize: 22 }}>{EMOTION_EMOJI[emotion] || '😐'}</span>
                    <span style={{ color: EMOTION_COLORS[emotion] || '#fff', fontSize: 15, fontWeight: 700 }}>
                      {emotion?.toUpperCase() || 'NEUTRAL'}
                    </span>
                  </div>
                  <div style={styles.stressRow}>
                    <span style={styles.dimText}>Stress</span>
                    <span style={{ color: stressColor, fontSize: 11, fontWeight: 700 }}>
                      {(stressLevel * 100).toFixed(0)}% — {stressLabel}
                    </span>
                  </div>
                  <div style={styles.track}>
                    <div style={{ ...styles.fill, width: `${stressLevel * 100}%`, background: stressColor }} />
                  </div>
                  {stressHistory.length > 3 && (
                    <div style={styles.stressRow}>
                      <span style={styles.dimText}>Session Avg</span>
                      <span style={{
                        color: avgStress >= 0.75 ? '#ef4444' : avgStress >= 0.4 ? '#f59e0b' : '#22c55e',
                        fontSize: 11, fontWeight: 700,
                      }}>
                        {(avgStress * 100).toFixed(0)}%
                      </span>
                    </div>
                  )}
                  {stressHistory.length > 1 && (
                    <>
                      <p style={{ ...styles.sectionTitle, marginTop: 8 }}>STRESS TIMELINE</p>
                      <div style={styles.historyBars}>
                        {stressHistory.slice(-15).map((s, i) => (
                          <div key={i} style={{
                            ...styles.historyBar,
                            height: `${Math.max(4, s * 50)}px`,
                            background: s >= 0.75 ? '#ef4444' : s >= 0.4 ? '#f59e0b' : '#22c55e',
                          }} />
                        ))}
                      </div>
                    </>
                  )}
                </>
              )}
            </div>

            {/* Contradictions */}
            {contradictions.length > 0 && (
              <div style={styles.section}>
                <p style={{ ...styles.sectionTitle, color: '#ef4444' }}>
                  ⚠ CONTRADICTIONS ({contradictions.length})
                </p>
                {contradictions.map((c, i) => (
                  <div key={i} style={{
                    ...styles.flagItem,
                    borderColor: c.severity === 'high' ? '#ef4444' : c.severity === 'medium' ? '#f59e0b' : '#888',
                  }}>
                    <span style={{
                      fontSize: 10, fontWeight: 700,
                      color: c.severity === 'high' ? '#ef4444' : '#f59e0b',
                    }}>
                      {c.severity?.toUpperCase()}
                    </span>
                    <p style={styles.flagDesc}>{c.description}</p>
                  </div>
                ))}
              </div>
            )}

            {/* Deception indicators */}
            {deceptionIndicators.length > 0 && (
              <div style={styles.section}>
                <p style={{ ...styles.sectionTitle, color: '#f59e0b' }}>
                  🔍 DECEPTION INDICATORS ({deceptionIndicators.length})
                </p>
                {deceptionIndicators.map((d, i) => (
                  <div key={i} style={{
                    ...styles.flagItem,
                    borderColor: d.severity === 'high' ? '#ef4444' : d.severity === 'medium' ? '#f59e0b' : '#666',
                  }}>
                    <span style={{ fontSize: 11 }}>
                      {d.emoji}{' '}
                      <span style={{ fontSize: 10, fontWeight: 700, color: '#ccc' }}>{d.title}</span>
                    </span>
                    <p style={styles.flagDesc}>{d.description}</p>
                  </div>
                ))}
              </div>
            )}

            {/* Evidence context */}
            {analysis && (
              <div style={styles.section}>
                <p style={styles.sectionTitle}>EVIDENCE</p>
                <p style={{ ...styles.dimText, lineHeight: 1.5, marginBottom: 8 }}>
                  {analysis.scene_summary || 'Scene analyzed.'}
                </p>
                {analysis.key_objects?.length > 0 && (
                  <div style={styles.tagRow}>
                    {analysis.key_objects.slice(0, 5).map((o, i) => (
                      <span key={i} style={styles.tag}>{o}</span>
                    ))}
                  </div>
                )}
              </div>
            )}

          </div>
        </div>

        {/* Right panel — chat */}
        <div style={styles.right}>
          <div style={styles.messages}>
            {messages.length === 0 && (
              <p style={styles.waiting}>Connecting...</p>
            )}
            {messages.map((m, i) => (
              <div key={i} style={{
                display: 'flex', flexDirection: 'column',
                alignItems: m.role === 'user' ? 'flex-end'
                  : m.role === 'system' ? 'center' : 'flex-start',
                marginBottom: 12,
              }}>
                {m.role === 'system' ? (
                  <div style={styles.sysMsg}>{m.content}</div>
                ) : (
                  <>
                    <div style={{
                      ...styles.bubble,
                      background: m.role === 'user' ? '#7c6af7' : '#1e1e32',
                      border: m.role === 'assistant' ? '1px solid #2a2a4a' : 'none',
                      maxWidth: '72%',
                    }}>
                      {m.role === 'assistant' && (
                        <span style={styles.aiLabel}>AI Interviewer</span>
                      )}
                      <p style={styles.bubbleText}>{m.content}</p>
                    </div>
                    {m.timestamp && (
                      <span style={{ fontSize: 10, color: '#444', marginTop: 3 }}>
                        {m.timestamp}
                      </span>
                    )}
                  </>
                )}
              </div>
            ))}
            {sending && (
              <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-start', marginBottom: 12 }}>
                <div style={{ ...styles.bubble, background: '#1e1e32', border: '1px solid #2a2a4a' }}>
                  <p style={{ ...styles.bubbleText, color: '#555' }}>AI is thinking...</p>
                </div>
              </div>
            )}
            <div ref={chatEndRef} />
          </div>

          {/* Input area */}
          {!complete ? (
            <div style={styles.inputArea}>

              {/* Language selector */}
              <div style={styles.langRow}>
                <span style={styles.langLabel}>Language:</span>
                {[
                  { code: 'en-IN', label: 'English' },
                  ,
                ].map((lang) => (
                  <button
                    key={lang.code}
                    style={{
                      ...styles.langBtn,
                      background:  language === lang.code ? '#7c6af7' : 'transparent',
                      color:       language === lang.code ? '#fff' : '#666',
                      border:      language === lang.code ? '1px solid #7c6af7' : '1px solid #2a2a4a',
                    }}
                    onClick={() => setLanguage(lang.code)}
                  >
                    {lang.label}
                  </button>
                ))}
                {listening && (
                  <span style={styles.listeningBadge}>🔴 Listening...</span>
                )}
              </div>

              {/* Input row */}
              <div style={styles.inputBar}>
                <input
                  style={{
                    ...styles.chatInput,
                    border: listening ? '2px solid #7c6af7' : '1px solid #2a2a4a',
                  }}
                  placeholder={
                    listening
                      ? '🎤 Listening... speak now'
                      : 'Type response or press 🎤 to speak...'
                  }
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && sendResponse()}
                  disabled={sending}
                />
                <button
                  style={{
                    ...styles.micBtn,
                    background: listening ? '#7c6af7' : '#1a1a2e',
                    color:      listening ? '#fff' : '#888',
                    border:     listening ? '1px solid #7c6af7' : '1px solid #2a2a4a',
                  }}
                  onClick={toggleListening}
                  title={listening ? 'Stop listening' : 'Start voice input'}
                  disabled={sending}
                >
                  {listening ? '⏹' : '🎤'}
                </button>
                <button
                  style={{ ...styles.sendBtn, opacity: sending ? 0.5 : 1 }}
                  onClick={sendResponse}
                  disabled={sending || !input.trim()}
                >
                  Send
                </button>
              </div>

            </div>
          ) : (
            <div style={styles.doneBar}>
              Interview complete —{' '}
              <span style={styles.doneLink} onClick={() => navigate(`/report/${sessionId}`)}>
                View full report →
              </span>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

const styles = {
  root:              { height: '100vh', display: 'flex', flexDirection: 'column', background: '#0f0f1a', fontFamily: 'system-ui, sans-serif', overflow: 'hidden' },
  header:            { flexShrink: 0, background: '#1a1a2e', borderBottom: '1px solid #2a2a4a', padding: '0.5rem 1.25rem', display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 12, flexWrap: 'wrap' },
  headerLeft:        { display: 'flex', alignItems: 'center', gap: 12 },
  logo:              { color: '#7c6af7', fontWeight: 700, fontSize: 16, letterSpacing: 2 },
  caseInfo:          { color: '#555', fontSize: 12 },
  headerRight:       { display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' },
  headerStress:      { display: 'flex', alignItems: 'center', gap: 6, background: '#0f0f1a', padding: '3px 8px', borderRadius: 6, border: '1px solid #2a2a4a' },
  headerStressLabel: { color: '#555', fontSize: 10, fontWeight: 600 },
  headerStressBar:   { width: 60, height: 5, background: '#2a2a4a', borderRadius: 3, overflow: 'hidden' },
  headerStressFill:  { height: '100%', borderRadius: 3, transition: 'width 0.5s, background 0.5s' },
  flagBadge:         { background: '#2a0a0a', color: '#ef4444', border: '1px solid #ef4444', padding: '3px 8px', borderRadius: 6, fontSize: 11, fontWeight: 700 },
  endBtn:            { background: '#ef444420', color: '#ef4444', border: '1px solid #ef4444', padding: '4px 10px', borderRadius: 6, cursor: 'pointer', fontSize: 11, fontWeight: 600 },
  reportBtn:         { background: 'transparent', color: '#7c6af7', border: '1px solid #7c6af7', padding: '4px 10px', borderRadius: 6, cursor: 'pointer', fontSize: 11, fontWeight: 600 },
  phaseBar:          { flexShrink: 0, background: '#1a1a2e', borderBottom: '1px solid #2a2a4a', padding: '0.5rem 1.5rem', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 0 },
  phaseItem:         { display: 'flex', alignItems: 'center', gap: 6 },
  phaseDot:          { width: 24, height: 24, borderRadius: '50%', border: '2px solid', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 10, fontWeight: 700, color: '#fff', flexShrink: 0 },
  phaseLabel:        { fontSize: 11, fontWeight: 600, whiteSpace: 'nowrap' },
  phaseLine:         { width: 30, height: 2, margin: '0 4px' },
  body:              { flex: 1, display: 'flex', overflow: 'hidden', minHeight: 0 },
  left:              { width: 270, flexShrink: 0, background: '#1a1a2e', borderRight: '1px solid #2a2a4a', display: 'flex', flexDirection: 'column', overflow: 'hidden' },
  camBox:            { position: 'relative', background: '#000', flexShrink: 0 },
  cam:               { width: '100%', aspectRatio: '4/3', display: 'block', objectFit: 'cover' },
  camLabel:          { position: 'absolute', bottom: 6, left: 8, background: '#00000099', color: '#fff', fontSize: 10, padding: '2px 6px', borderRadius: 4 },
  leftScroll:        { flex: 1, overflowY: 'auto' },
  section:           { padding: '0.65rem 0.75rem', borderBottom: '1px solid #1a1a2e' },
  sectionTitle:      { color: '#555', fontSize: 9, fontWeight: 700, letterSpacing: 1, margin: '0 0 6px' },
  dimText:           { color: '#555', fontSize: 11, margin: 0 },
  emotionRow:        { display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 },
  stressRow:         { display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 4 },
  track:             { height: 6, background: '#2a2a4a', borderRadius: 3, overflow: 'hidden', marginBottom: 6 },
  fill:              { height: '100%', borderRadius: 3, transition: 'width 0.5s, background 0.5s' },
  historyBars:       { display: 'flex', alignItems: 'flex-end', gap: 2, height: 40, marginTop: 4 },
  historyBar:        { flex: 1, borderRadius: 2, minHeight: 3 },
  flagItem:          { borderLeft: '3px solid', paddingLeft: 8, marginBottom: 8 },
  flagDesc:          { color: '#888', fontSize: 10, margin: '2px 0 0', lineHeight: 1.4 },
  tagRow:            { display: 'flex', flexWrap: 'wrap', gap: 4 },
  tag:               { background: '#0f0f1a', border: '1px solid #2a2a4a', color: '#555', padding: '2px 5px', borderRadius: 3, fontSize: 9 },
  right:             { flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden', minWidth: 0 },
  messages:          { flex: 1, overflowY: 'auto', padding: '1rem 1.25rem', minHeight: 0 },
  waiting:           { color: '#444', textAlign: 'center', marginTop: 60, fontSize: 14 },
  bubble:            { borderRadius: 12, padding: '10px 14px' },
  aiLabel:           { display: 'block', color: '#7c6af7', fontSize: 11, fontWeight: 700, marginBottom: 4 },
  bubbleText:        { color: '#fff', fontSize: 14, margin: 0, lineHeight: 1.55 },
  sysMsg:            { background: '#2a2a4a', color: '#777', fontSize: 12, padding: '5px 14px', borderRadius: 20 },
  inputArea:         { flexShrink: 0, background: '#1a1a2e', borderTop: '1px solid #2a2a4a' },
  langRow:           { display: 'flex', alignItems: 'center', gap: 6, padding: '0.4rem 1rem 0' },
  langLabel:         { color: '#555', fontSize: 10, fontWeight: 600 },
  langBtn:           { padding: '2px 8px', borderRadius: 5, cursor: 'pointer', fontSize: 10, fontWeight: 600 },
  listeningBadge:    { color: '#ef4444', fontSize: 11, fontWeight: 700, marginLeft: 8, animation: 'pulse 1s infinite' },
  inputBar:          { display: 'flex', gap: 8, padding: '0.5rem 1rem 0.75rem' },
  chatInput:         { flex: 1, padding: '10px 14px', background: '#0f0f1a', borderRadius: 8, color: '#fff', fontSize: 14, outline: 'none', transition: 'border 0.2s' },
  micBtn:            { padding: '10px 14px', borderRadius: 8, cursor: 'pointer', fontSize: 14, fontWeight: 600, transition: 'all 0.2s' },
  sendBtn:           { background: '#7c6af7', color: '#fff', border: 'none', padding: '10px 18px', borderRadius: 8, cursor: 'pointer', fontSize: 14, fontWeight: 600 },
  doneBar:           { flexShrink: 0, padding: '0.75rem 1.25rem', background: '#1a1a2e', borderTop: '1px solid #2a2a4a', color: '#777', fontSize: 14, textAlign: 'center' },
  doneLink:          { color: '#7c6af7', cursor: 'pointer', fontWeight: 600 },
}