import { useEffect, useRef, useState, useCallback } from 'react'
import axios from 'axios'
import './TimelineBar.css'

const getApiUrl = () => {
  if (import.meta.env.VITE_API_URL) return import.meta.env.VITE_API_URL
  const port = window.location.port
  if (port === '' || port === '80' || port === '443') return window.location.origin
  return 'http://localhost:8000'
}
const API_URL = getApiUrl()

/**
 * Full-recording overview bar with envelope, seizure markers, and
 * a draggable viewport indicator.
 *
 * Props:
 *   dataset        — current dataset object (must have .id, .duration, .metadata)
 *   viewportStart  — current viewport start in seconds
 *   viewportDuration — current viewport width in seconds
 *   onViewportChange(start) — called when user clicks/drags the viewport
 *   annotations    — array of annotations (seizure detections etc.)
 */
function TimelineBar({ dataset, viewportStart, viewportDuration, onViewportChange, annotations }) {
  const canvasRef = useRef(null)
  const [envelope, setEnvelope] = useState(null)
  const [loading, setLoading] = useState(false)
  const [dragging, setDragging] = useState(false)
  const dragStartRef = useRef(null)

  const isH5 = dataset?.metadata?.is_h5_ref === true

  // Fetch envelope when dataset changes
  useEffect(() => {
    if (!dataset || !isH5) {
      setEnvelope(null)
      return
    }
    let cancelled = false
    const fetchEnvelope = async () => {
      setLoading(true)
      try {
        const resp = await axios.get(`${API_URL}/api/datasets/${dataset.id}/envelope`, {
          params: { points: 2000 }
        })
        if (!cancelled) setEnvelope(resp.data)
      } catch (err) {
        console.warn('Could not load envelope:', err.message)
      } finally {
        if (!cancelled) setLoading(false)
      }
    }
    fetchEnvelope()
    return () => { cancelled = true }
  }, [dataset?.id, isH5])

  // Render canvas
  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas || !dataset) return
    const ctx = canvas.getContext('2d')
    const w = canvas.width
    const h = canvas.height
    const duration = dataset.metadata?.duration || dataset.duration || 1

    ctx.clearRect(0, 0, w, h)

    // Background
    ctx.fillStyle = '#1a1a2e'
    ctx.fillRect(0, 0, w, h)

    // Draw envelope
    if (envelope && envelope.times.length > 0) {
      const times = envelope.times
      const nCh = envelope.n_channels
      // Draw first channel envelope as filled area
      const envMin = envelope.env_min[0]
      const envMax = envelope.env_max[0]

      // Find data range for scaling
      let dataMin = Infinity, dataMax = -Infinity
      for (let i = 0; i < envMin.length; i++) {
        if (envMin[i] < dataMin) dataMin = envMin[i]
        if (envMax[i] > dataMax) dataMax = envMax[i]
      }
      const dataRange = (dataMax - dataMin) || 1

      ctx.fillStyle = 'rgba(100, 180, 255, 0.3)'
      ctx.strokeStyle = 'rgba(100, 180, 255, 0.6)'
      ctx.lineWidth = 1

      ctx.beginPath()
      for (let i = 0; i < times.length; i++) {
        const x = (times[i] / duration) * w
        const yMin = h - ((envMin[i] - dataMin) / dataRange) * h * 0.8 - h * 0.1
        if (i === 0) ctx.moveTo(x, yMin)
        else ctx.lineTo(x, yMin)
      }
      for (let i = times.length - 1; i >= 0; i--) {
        const x = (times[i] / duration) * w
        const yMax = h - ((envMax[i] - dataMin) / dataRange) * h * 0.8 - h * 0.1
        ctx.lineTo(x, yMax)
      }
      ctx.closePath()
      ctx.fill()
      ctx.stroke()
    }

    // Draw seizure annotations as red markers
    const allSeizures = [
      ...(envelope?.seizures || []),
      ...(annotations || []).filter(a =>
        a.description?.toLowerCase().includes('seizure')
      ).map(a => ({ onset: a.onset, offset: a.onset + a.duration }))
    ]

    for (const sz of allSeizures) {
      const x1 = (sz.onset / duration) * w
      const x2 = ((sz.offset ?? (sz.onset + (sz.duration || 10))) / duration) * w
      ctx.fillStyle = 'rgba(255, 60, 60, 0.5)'
      ctx.fillRect(x1, 0, Math.max(x2 - x1, 2), h)
      // Triangle marker at top
      ctx.fillStyle = '#ff3c3c'
      ctx.beginPath()
      ctx.moveTo((x1 + x2) / 2, 0)
      ctx.lineTo((x1 + x2) / 2 - 4, 6)
      ctx.lineTo((x1 + x2) / 2 + 4, 6)
      ctx.closePath()
      ctx.fill()
    }

    // Draw viewport indicator
    const vpX = (viewportStart / duration) * w
    const vpW = Math.max((viewportDuration / duration) * w, 4)

    ctx.fillStyle = 'rgba(255, 255, 255, 0.15)'
    ctx.fillRect(vpX, 0, vpW, h)
    ctx.strokeStyle = '#fff'
    ctx.lineWidth = 2
    ctx.strokeRect(vpX, 0, vpW, h)

    // Time labels
    ctx.fillStyle = '#888'
    ctx.font = '10px monospace'
    ctx.textBaseline = 'bottom'
    const nLabels = Math.min(10, Math.floor(w / 80))
    for (let i = 0; i <= nLabels; i++) {
      const t = (i / nLabels) * duration
      const x = (i / nLabels) * w
      const label = t >= 3600
        ? `${(t / 3600).toFixed(1)}h`
        : `${(t / 60).toFixed(0)}m`
      ctx.fillText(label, x + 2, h - 2)
    }
  }, [envelope, dataset, viewportStart, viewportDuration, annotations])

  // Click/drag to set viewport position
  const handleMouseDown = useCallback((e) => {
    const canvas = canvasRef.current
    if (!canvas || !dataset) return
    const rect = canvas.getBoundingClientRect()
    const x = e.clientX - rect.left
    const frac = x / canvas.width
    const duration = dataset.metadata?.duration || dataset.duration || 1
    const newStart = Math.max(0, frac * duration - viewportDuration / 2)
    onViewportChange?.(Math.min(newStart, duration - viewportDuration))
    setDragging(true)
    dragStartRef.current = x
  }, [dataset, viewportDuration, onViewportChange])

  const handleMouseMove = useCallback((e) => {
    if (!dragging) return
    const canvas = canvasRef.current
    if (!canvas || !dataset) return
    const rect = canvas.getBoundingClientRect()
    const x = e.clientX - rect.left
    const frac = x / canvas.width
    const duration = dataset.metadata?.duration || dataset.duration || 1
    const newStart = Math.max(0, frac * duration - viewportDuration / 2)
    onViewportChange?.(Math.min(newStart, duration - viewportDuration))
  }, [dragging, dataset, viewportDuration, onViewportChange])

  const handleMouseUp = useCallback(() => {
    setDragging(false)
  }, [])

  // Global mouse up listener for drag release
  useEffect(() => {
    if (dragging) {
      window.addEventListener('mouseup', handleMouseUp)
      window.addEventListener('mousemove', handleMouseMove)
      return () => {
        window.removeEventListener('mouseup', handleMouseUp)
        window.removeEventListener('mousemove', handleMouseMove)
      }
    }
  }, [dragging, handleMouseUp, handleMouseMove])

  if (!dataset) return null

  // For non-H5 datasets, show a simple timeline without envelope
  const duration = dataset.metadata?.duration || dataset.duration || 1

  return (
    <div className="timeline-bar-container">
      <div className="timeline-bar-label">
        {isH5 && (
          <span className="timeline-badge">H5 LAZY</span>
        )}
        <span className="timeline-duration">
          {duration >= 3600
            ? `${(duration / 3600).toFixed(1)}h`
            : `${(duration / 60).toFixed(1)}m`
          }
          {envelope?.seizures?.length > 0 && (
            <span className="timeline-seizure-count">
              {' '} · {envelope.seizures.length} seizures
            </span>
          )}
        </span>
      </div>
      <canvas
        ref={canvasRef}
        className="timeline-bar-canvas"
        width={800}
        height={40}
        onMouseDown={handleMouseDown}
        style={{ cursor: dragging ? 'grabbing' : 'pointer' }}
      />
      {loading && <div className="timeline-loading">Loading envelope…</div>}
    </div>
  )
}

export default TimelineBar
