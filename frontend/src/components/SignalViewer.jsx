import { useEffect, useRef, useState } from 'react'
import axios from 'axios'
import './SignalViewer.css'

// API URL from environment variable, fallback to localhost
const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

function SignalViewer({ dataset, annotations, customAnnotationTypes, onAnnotationCreate }) {
  console.log('SignalViewer rendered')
  console.log('Dataset:', dataset)
  console.log('Dataset metadata:', dataset?.metadata)
  
  const canvasRef = useRef(null)
  const containerRef = useRef(null)
  const [signalData, setSignalData] = useState(null)
  const [viewportStart, setViewportStart] = useState(0)
  const [viewportDuration, setViewportDuration] = useState(5)  // Default to 5 seconds
  const [amplitudeScale, setAmplitudeScale] = useState(1.0)  // 1.0 = normal, >1 = bigger, <1 = smaller
  const [loading, setLoading] = useState(false)
  const [isDragging, setIsDragging] = useState(false)
  const [dragStart, setDragStart] = useState(null)
  const [selectedDescription, setSelectedDescription] = useState('BAD_artifact')  // For new annotations
  const [maxChannelsToShow, setMaxChannelsToShow] = useState(20)  // Limit initially for performance

  // Load signal data when viewport changes
  useEffect(() => {
    if (!dataset) {
      console.log('No dataset selected')
      return
    }
    console.log('Dataset changed, loading data for:', dataset.id)
    loadSignalData()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [dataset, viewportStart, viewportDuration])

  // Render canvas when data or annotations change
  useEffect(() => {
    if (signalData) {
      console.log('Signal data or annotations changed, rendering canvas')
      console.log('Annotations to render:', annotations.length, annotations)
      renderCanvas()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [signalData, annotations, amplitudeScale, selectedDescription, maxChannelsToShow])

  const loadSignalData = async () => {
    console.log('=== loadSignalData called ===')
    console.log('Dataset ID:', dataset?.id)
    console.log('API_URL:', API_URL)
    
    setLoading(true)
    try {
      console.log('Loading signal data...')
      const url = `${API_URL}/api/datasets/${dataset.id}/data`
      console.log('Request URL:', url)
      
      const response = await axios.get(url, {
        params: {
          start_time: viewportStart,
          duration: viewportDuration,
          downsample: 2
        }
      })
      console.log('Response received:', response.data)
      console.log('Signal data loaded:', response.data.channel_names?.length, 'channels')
      setSignalData(response.data)
    } catch (error) {
      console.error('Error loading signal data:', error)
      console.error('Error details:', error.response?.data)
      alert('Error loading signal data: ' + (error.response?.data?.detail || error.message))
    } finally {
      setLoading(false)
    }
  }

  const renderCanvas = () => {
    try {
      console.log('Rendering canvas...')
      const canvas = canvasRef.current
      if (!canvas || !signalData) {
        console.log('Canvas or signal data not ready')
        return
      }

      const ctx = canvas.getContext('2d')
      if (!ctx) {
        console.error('Could not get canvas context')
        return
      }

      const totalChannels = signalData.channel_names.length
      console.log('Total channels to render:', totalChannels)
      if (totalChannels === 0) return
      
      // Limit channels for performance - render only the first maxChannelsToShow
      const channelsToRender = Math.min(totalChannels, maxChannelsToShow)
      console.log('Rendering', channelsToRender, 'of', totalChannels, 'channels')
      
      // Set canvas size to accommodate visible channels
      const channelHeight = 60  // Reduced from 80 to 60 for better performance
      const width = canvas.width
      const height = channelsToRender * channelHeight
      
      console.log('Canvas dimensions:', width, 'x', height)
      
      // Only update canvas height if it changed (to prevent unnecessary resets)
      if (canvas.height !== height) {
        canvas.height = height
      }

      // Clear canvas
      ctx.fillStyle = 'white'
      ctx.fillRect(0, 0, width, height)

    const pixelsPerSecond = width / viewportDuration

    // Render limited number of channels first
    for (let i = 0; i < channelsToRender; i++) {
      const channelName = signalData.channel_names[i]
      const yOffset = (i + 0.5) * channelHeight
      const channelData = signalData.data[i]

      if (!channelData || channelData.length === 0) continue

      // Draw channel background
      if (i % 2 === 0) {
        ctx.fillStyle = '#fafafa'
        ctx.fillRect(0, i * channelHeight, width, channelHeight)
      }

      // Draw channel label with background
      ctx.fillStyle = 'rgba(255, 255, 255, 0.9)'
      ctx.fillRect(0, i * channelHeight, 100, 20)
      ctx.fillStyle = '#333'
      ctx.font = 'bold 12px Arial'
      ctx.fillText(channelName, 5, i * channelHeight + 15)

      // Draw center line for this channel
      ctx.strokeStyle = '#e8e8e8'
      ctx.lineWidth = 1
      ctx.beginPath()
      ctx.moveTo(100, yOffset)
      ctx.lineTo(width, yOffset)
      ctx.stroke()

      // Calculate signal bounds for this channel to normalize properly
      const maxVal = Math.max(...channelData.map(Math.abs))
      const baseScale = maxVal > 0 ? (channelHeight * 0.35) / maxVal : 1
      
      // Apply user's amplitude adjustment (multiply to scale up/down)
      const finalScale = baseScale * amplitudeScale

      // Draw signal - constrained within this channel's bounds
      ctx.strokeStyle = '#2196F3'
      ctx.lineWidth = 1.5
      ctx.beginPath()

      let pathStarted = false
      channelData.forEach((value, idx) => {
        // Use exact time from data, properly offset by viewport start
        const timeValue = signalData.times[idx]
        const x = (timeValue - viewportStart) * pixelsPerSecond
        
        // Skip points outside viewport to avoid rendering artifacts
        if (x < 0 || x > width) return
        
        // Clamp y to stay within channel bounds
        const rawY = yOffset - (value * finalScale)
        const minY = i * channelHeight + 5
        const maxY = (i + 1) * channelHeight - 5
        const y = Math.max(minY, Math.min(maxY, rawY))

        if (!pathStarted) {
          ctx.moveTo(x, y)
          pathStarted = true
        } else {
          ctx.lineTo(x, y)
        }
      })
      ctx.stroke()

      // Draw channel separator
      if (i < channelsToRender - 1) {
        ctx.strokeStyle = '#e0e0e0'
        ctx.lineWidth = 1
        ctx.beginPath()
        ctx.moveTo(0, (i + 1) * channelHeight)
        ctx.lineTo(width, (i + 1) * channelHeight)
        ctx.stroke()
      }
    }

    // Draw time axis
    ctx.fillStyle = '#666'
    ctx.font = '11px Arial'
    const timeStart = Math.floor(viewportStart)
    const timeEnd = Math.ceil(viewportStart + viewportDuration)
    
    for (let t = timeStart; t <= timeEnd; t++) {
      // Skip if time is outside our actual viewport
      if (t < viewportStart || t > viewportStart + viewportDuration) continue
      
      const x = (t - viewportStart) * pixelsPerSecond
      
      // Only draw if x is within canvas bounds
      if (x >= 0 && x <= width) {
        ctx.fillText(`${t}s`, x + 2, height - 5)
        ctx.strokeStyle = '#ccc'
        ctx.lineWidth = 1
        ctx.beginPath()
        ctx.moveTo(x, 0)
        ctx.lineTo(x, height)
        ctx.stroke()
      }
    }
    
    // Render annotations ON TOP of signals and time axis (so labels are visible)
    renderAnnotations(ctx, pixelsPerSecond, height)
    
    console.log('Canvas rendering complete')
    } catch (error) {
      console.error('Error rendering canvas:', error)
      alert('Error rendering canvas: ' + error.message)
    }
  }

  const renderAnnotations = (ctx, pixelsPerSecond, height) => {
    const viewportEnd = viewportStart + viewportDuration

    console.log('Rendering annotations:', annotations.length, 'annotations total')
    annotations.forEach((ann, idx) => {
      // Skip if annotation is outside viewport
      if (ann.onset + ann.duration < viewportStart || ann.onset > viewportEnd) {
        console.log(`  Annotation ${idx} outside viewport:`, ann)
        return
      }

      console.log(`  Rendering annotation ${idx}:`, ann.description, 'at', ann.onset, 'for', ann.duration, 's')

      const x = (ann.onset - viewportStart) * pixelsPerSecond
      const width = ann.duration * pixelsPerSecond

      console.log(`  Position: x=${x}, width=${width}`)

      // Color based on description
      let color = 'rgba(255, 193, 7, 0.3)'  // Yellow for default
      let borderColor = 'rgba(255, 193, 7, 1.0)'
      
      if (ann.description.startsWith('BAD')) {
        color = 'rgba(244, 67, 54, 0.3)'  // Red for BAD
        borderColor = 'rgba(244, 67, 54, 1.0)'
      } else if (ann.description.includes('Blink') || ann.description.includes('blink')) {
        color = 'rgba(76, 175, 80, 0.3)'  // Green for Blink
        borderColor = 'rgba(76, 175, 80, 1.0)'
      } else if (ann.description.includes('Movement') || ann.description.includes('movement')) {
        color = 'rgba(33, 150, 243, 0.3)'  // Blue for Movement
        borderColor = 'rgba(33, 150, 243, 1.0)'
      }

      // Draw annotation rectangle
      ctx.fillStyle = color
      ctx.fillRect(x, 0, width, height)

      // Draw border
      ctx.strokeStyle = borderColor
      ctx.lineWidth = 2
      ctx.strokeRect(x, 0, width, height)

      // Draw label with background for better visibility
      ctx.font = 'bold 12px Arial'
      const labelText = `${ann.description} (${ann.duration.toFixed(2)}s)`
      const textMetrics = ctx.measureText(labelText)
      const textWidth = textMetrics.width
      const textHeight = 16
      
      // Draw label background
      ctx.fillStyle = 'rgba(255, 255, 255, 0.9)'
      ctx.fillRect(x + 5, 5, textWidth + 6, textHeight)
      
      // Draw label text
      ctx.fillStyle = '#000'
      ctx.fillText(labelText, x + 8, 17)
    })
  }

  const handleMouseDown = (e) => {
    const canvas = canvasRef.current
    const rect = canvas.getBoundingClientRect()
    // Use the actual displayed width from bounding rect, not canvas.width
    const x = e.clientX - rect.left
    const time = viewportStart + (x / rect.width) * viewportDuration

    setIsDragging(true)
    setDragStart({ x, time })
  }

  const handleMouseMove = (e) => {
    if (!isDragging || !dragStart) return

    const canvas = canvasRef.current
    const rect = canvas.getBoundingClientRect()
    const currentX = e.clientX - rect.left

    // Re-render with preview
    renderCanvas()
    const ctx = canvas.getContext('2d')
    
    // Calculate current time from mouse position
    const currentTime = viewportStart + (currentX / rect.width) * viewportDuration
    const previewDuration = Math.abs(currentTime - dragStart.time)
    const previewStart = Math.min(dragStart.time, currentTime)
    
    // Convert time coordinates to canvas pixel coordinates
    const pixelsPerSecond = canvas.width / viewportDuration
    const startXCanvas = (previewStart - viewportStart) * pixelsPerSecond
    const widthCanvas = previewDuration * pixelsPerSecond

    // Draw preview rectangle
    ctx.fillStyle = 'rgba(33, 150, 243, 0.4)'
    ctx.fillRect(startXCanvas, 0, widthCanvas, canvas.height)
    
    // Draw preview label
    ctx.font = 'bold 12px Arial'
    const labelText = `${selectedDescription} (${previewDuration.toFixed(2)}s)`
    const textMetrics = ctx.measureText(labelText)
    
    // Draw label background
    ctx.fillStyle = 'rgba(255, 255, 255, 0.9)'
    ctx.fillRect(startXCanvas + 5, 5, textMetrics.width + 6, 16)
    
    // Draw label text
    ctx.fillStyle = '#000'
    ctx.fillText(labelText, startXCanvas + 8, 17)
  }

  const handleMouseUp = (e) => {
    if (!isDragging || !dragStart) return

    const canvas = canvasRef.current
    const rect = canvas.getBoundingClientRect()
    const endX = e.clientX - rect.left
    const endTime = viewportStart + (endX / rect.width) * viewportDuration

    const onset = Math.min(dragStart.time, endTime)
    const duration = Math.abs(endTime - dragStart.time)

    if (duration > 0.1) {
      onAnnotationCreate?.({ 
        onset, 
        duration,
        description: selectedDescription  // Use selected description
      })
    }

    setIsDragging(false)
    setDragStart(null)
    renderCanvas()
  }

  const panLeft = () => {
    setViewportStart(Math.max(0, viewportStart - viewportDuration * 0.5))
  }

  const panRight = () => {
    const maxStart = dataset.duration - viewportDuration
    setViewportStart(Math.min(maxStart, viewportStart + viewportDuration * 0.5))
  }

  const zoomIn = () => {
    setViewportDuration(Math.max(1, viewportDuration / 1.5))
  }

  const zoomOut = () => {
    setViewportDuration(Math.min(dataset.duration, viewportDuration * 1.5))
  }

  const scaleUp = () => {
    setAmplitudeScale(amplitudeScale * 1.5)  // Make signals bigger
  }

  const scaleDown = () => {
    setAmplitudeScale(amplitudeScale / 1.5)  // Make signals smaller
  }

  const showMoreChannels = () => {
    const totalChannels = signalData?.channel_names.length || 0
    setMaxChannelsToShow(Math.min(totalChannels, maxChannelsToShow + 20))
  }

  const showFewerChannels = () => {
    setMaxChannelsToShow(Math.max(10, maxChannelsToShow - 20))
  }

  const showAllChannels = () => {
    const totalChannels = signalData?.channel_names.length || 0
    setMaxChannelsToShow(totalChannels)
  }
  
  // Base annotation types
  const baseAnnotationTypes = [
    'BAD_artifact',
    'BAD_blink',
    'BAD_movement',
    'Blink',
    'Movement',
    'Sleep_spindle',
    'K_complex'
  ]
  
  // Combine with custom types
  const allAnnotationTypes = [...baseAnnotationTypes, ...(customAnnotationTypes || [])]

  return (
    <div className="signal-viewer card">
      <h3>Signal Viewer - {dataset?.filename || 'No dataset'}</h3>
      
      <div className="viewer-toolbar">
        <div className="toolbar-group">
          <label style={{fontSize: '11px', marginRight: '5px'}}>Time:</label>
          <button className="secondary-btn" onClick={panLeft}>⬅️ Left</button>
          <button className="secondary-btn" onClick={panRight}>Right ➡️</button>
          <button className="secondary-btn" onClick={zoomIn}>🔍 Zoom In</button>
          <button className="secondary-btn" onClick={zoomOut}>🔎 Zoom Out</button>
        </div>
        <div className="toolbar-group">
          <label style={{fontSize: '11px', marginRight: '5px'}}>Amplitude:</label>
          <button className="secondary-btn" onClick={scaleUp}>⬆️ Bigger</button>
          <button className="secondary-btn" onClick={scaleDown}>⬇️ Smaller</button>
        </div>
        <div className="toolbar-group">
          <label style={{fontSize: '11px', marginRight: '5px'}}>Channels:</label>
          <button className="secondary-btn" onClick={showFewerChannels}>➖ Fewer</button>
          <button className="secondary-btn" onClick={showMoreChannels}>➕ More</button>
          <button className="secondary-btn" onClick={showAllChannels}>Show All</button>
        </div>
        <div className="toolbar-group">
          <label style={{fontSize: '11px', marginRight: '5px'}}>Annotation Type:</label>
          <select 
            value={selectedDescription} 
            onChange={(e) => setSelectedDescription(e.target.value)}
            style={{padding: '4px 8px', borderRadius: '4px', border: '1px solid #ccc'}}
          >
            {allAnnotationTypes.map(type => (
              <option key={type} value={type}>{type}</option>
            ))}
          </select>
        </div>
        <div className="toolbar-info">
          <span>Time: {viewportStart.toFixed(1)}s - {(viewportStart + viewportDuration).toFixed(1)}s</span>
          <span>Showing: {maxChannelsToShow} of {signalData?.channel_names.length || 0} channels</span>
          <span>Amplitude: {amplitudeScale.toFixed(2)}x</span>
        </div>
      </div>

      {loading && <div className="loading-overlay">⏳ Loading data...</div>}

      {/* Time scrollbar */}
      {dataset && dataset.metadata && (
        <div style={{ marginBottom: '10px' }}>
          <label style={{ fontSize: '12px', fontWeight: 'bold', marginBottom: '5px', display: 'block' }}>
            Time Navigation: {viewportStart.toFixed(1)}s / {dataset.metadata.duration?.toFixed(1) || '?'}s
          </label>
          <input
            type="range"
            min="0"
            max={Math.max(0, (dataset.metadata.duration || 0) - viewportDuration)}
            step="0.1"
            value={viewportStart}
            onChange={(e) => setViewportStart(parseFloat(e.target.value))}
            style={{ width: '100%', cursor: 'pointer' }}
          />
        </div>
      )}

      <div className="canvas-container" style={{ maxHeight: '600px', overflowY: 'auto', overflowX: 'hidden' }}>
        <canvas
          ref={canvasRef}
          width={1200}
          height={600}
          onMouseDown={handleMouseDown}
          onMouseMove={handleMouseMove}
          onMouseUp={handleMouseUp}
          onMouseLeave={handleMouseUp}
          style={{ cursor: isDragging ? 'col-resize' : 'crosshair', display: 'block' }}
        />
      </div>

      <div className="viewer-instructions">
        💡 <strong>Tip:</strong> Click and drag horizontally to create a "{selectedDescription}" annotation. Scroll vertically to see all channels.
      </div>
    </div>
  )
}

export default SignalViewer
