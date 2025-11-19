import { useEffect, useRef, useState, useCallback } from 'react'
import axios from 'axios'
import './SignalViewer.css'

const API_URL = 'http://localhost:8000'

function SignalViewer({ dataset, annotations, customAnnotationTypes, onAnnotationCreate, onAnnotationsRefresh, socket, currentUser }) {
  console.log('SignalViewer component rendered with dataset:', dataset?.id)
  
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
  const [selectedAnnotation, setSelectedAnnotation] = useState(null)  // Currently selected annotation for editing
  const [dragMode, setDragMode] = useState(null)  // 'left', 'right', 'move', or null
  const [editingAnnotation, setEditingAnnotation] = useState(null)  // Copy of annotation being edited
  
  // Refs for performance optimization
  const debounceTimerRef = useRef(null)
  const rafIdRef = useRef(null)
  const lastViewportStartRef = useRef(viewportStart)

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
    setLoading(true)
    try {
      // Validate parameters before sending - check for NaN and infinity
      if (!isFinite(viewportStart) || !isFinite(viewportDuration)) {
        console.error('Invalid viewport values:', { viewportStart, viewportDuration })
        setLoading(false)
        return
      }
      
      const startTime = Math.max(0, viewportStart)
      const duration = Math.max(0.1, Math.min(viewportDuration, dataset.duration || 3600))
      
      console.log('Loading signal data with params:', {
        start_time: startTime,
        duration: duration,
        dataset_id: dataset.id,
        dataset_duration: dataset.duration
      })
      
      const response = await axios.get(
        `${API_URL}/api/datasets/${dataset.id}/data`,
        {
          params: {
            start_time: startTime,
            duration: duration,
            downsample: 2
          }
        }
      )
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

      // Check if this annotation is selected
      const isSelected = selectedAnnotation && selectedAnnotation.id === ann.id

      // Draw annotation rectangle
      ctx.fillStyle = color
      ctx.fillRect(x, 0, width, height)

      // Draw border (thicker if selected)
      ctx.strokeStyle = isSelected ? '#ff9800' : borderColor
      ctx.lineWidth = isSelected ? 4 : 2
      ctx.strokeRect(x, 0, width, height)

      // Draw drag handles if selected
      if (isSelected) {
        const handleWidth = 8
        ctx.fillStyle = '#ff9800'
        // Left handle
        ctx.fillRect(x - handleWidth / 2, height / 2 - 20, handleWidth, 40)
        // Right handle
        ctx.fillRect(x + width - handleWidth / 2, height / 2 - 20, handleWidth, 40)
        // Move indicator (top center)
        ctx.fillRect(x + width / 2 - 15, 0, 30, 8)
      }

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

  const handleMouseHover = (e) => {
    if (isDragging) return
    
    const canvas = canvasRef.current
    if (!canvas) return
    
    const rect = canvas.getBoundingClientRect()
    const x = e.clientX - rect.left
    const time = viewportStart + (x / rect.width) * viewportDuration
    const pixelsPerSecond = rect.width / viewportDuration

    // Check if hovering over an annotation
    const hoveredAnnotation = annotations.find(ann => {
      if (ann.onset + ann.duration < viewportStart || ann.onset > viewportStart + viewportDuration) {
        return false
      }
      const annX = (ann.onset - viewportStart) * pixelsPerSecond
      const annWidth = ann.duration * pixelsPerSecond
      return x >= annX && x <= annX + annWidth
    })

    if (hoveredAnnotation) {
      const annX = (hoveredAnnotation.onset - viewportStart) * pixelsPerSecond
      const annWidth = hoveredAnnotation.duration * pixelsPerSecond
      const handleZone = 10

      if (x < annX + handleZone) {
        canvas.style.cursor = 'ew-resize' // Left edge
      } else if (x > annX + annWidth - handleZone) {
        canvas.style.cursor = 'ew-resize' // Right edge
      } else {
        canvas.style.cursor = 'move' // Middle
      }
    } else {
      canvas.style.cursor = 'crosshair' // Default for creating new
    }
  }

  const handleMouseDown = (e) => {
    const canvas = canvasRef.current
    const rect = canvas.getBoundingClientRect()
    const x = e.clientX - rect.left
    const time = viewportStart + (x / rect.width) * viewportDuration
    const pixelsPerSecond = rect.width / viewportDuration

    // Check if clicking on an existing annotation
    const clickedAnnotation = annotations.find(ann => {
      if (ann.onset + ann.duration < viewportStart || ann.onset > viewportStart + viewportDuration) {
        return false
      }
      const annX = (ann.onset - viewportStart) * pixelsPerSecond
      const annWidth = ann.duration * pixelsPerSecond
      return x >= annX && x <= annX + annWidth
    })

    if (clickedAnnotation) {
      // Check if clicking on edges or middle
      const annX = (clickedAnnotation.onset - viewportStart) * pixelsPerSecond
      const annWidth = clickedAnnotation.duration * pixelsPerSecond
      const handleZone = 10 // pixels

      if (x < annX + handleZone) {
        // Left edge
        setDragMode('left')
      } else if (x > annX + annWidth - handleZone) {
        // Right edge
        setDragMode('right')
      } else {
        // Middle - move entire annotation
        setDragMode('move')
      }

      setSelectedAnnotation(clickedAnnotation)
      setEditingAnnotation({ ...clickedAnnotation })
      setIsDragging(true)
      setDragStart({ x, time })
    } else {
      // Creating new annotation
      setSelectedAnnotation(null)
      setDragMode(null)
      setEditingAnnotation(null)
      setIsDragging(true)
      setDragStart({ x, time })
    }
  }

  const handleMouseMove = (e) => {
    if (!isDragging || !dragStart) return

    // Cancel any pending animation frame
    if (rafIdRef.current) {
      cancelAnimationFrame(rafIdRef.current)
    }

    // Throttle re-renders using requestAnimationFrame
    rafIdRef.current = requestAnimationFrame(() => {
      const canvas = canvasRef.current
      const rect = canvas.getBoundingClientRect()
      const currentX = e.clientX - rect.left
      const currentTime = viewportStart + (currentX / rect.width) * viewportDuration

      // Re-render base canvas
      renderCanvas()
      const ctx = canvas.getContext('2d')
      const pixelsPerSecond = canvas.width / viewportDuration

      if (editingAnnotation && dragMode) {
        // Editing existing annotation
        let previewOnset = editingAnnotation.onset
        let previewDuration = editingAnnotation.duration

        if (dragMode === 'left') {
          // Adjust start time
          const newOnset = currentTime
          const newDuration = (editingAnnotation.onset + editingAnnotation.duration) - newOnset
          if (newDuration > 0.1) {
            previewOnset = newOnset
            previewDuration = newDuration
          }
        } else if (dragMode === 'right') {
          // Adjust end time
          const newDuration = currentTime - editingAnnotation.onset
          if (newDuration > 0.1) {
            previewDuration = newDuration
          }
        } else if (dragMode === 'move') {
          // Move entire annotation
          const timeDelta = currentTime - dragStart.time
          previewOnset = editingAnnotation.onset + timeDelta
        }

        // Draw preview of edited annotation
        const previewX = (previewOnset - viewportStart) * pixelsPerSecond
        const previewWidth = previewDuration * pixelsPerSecond

        ctx.fillStyle = 'rgba(255, 152, 0, 0.5)'
        ctx.fillRect(previewX, 0, previewWidth, canvas.height)
        ctx.strokeStyle = '#ff9800'
        ctx.lineWidth = 3
        ctx.strokeRect(previewX, 0, previewWidth, canvas.height)

        // Draw preview label
        ctx.font = 'bold 12px Arial'
        const labelText = `${editingAnnotation.description} (${previewDuration.toFixed(2)}s)`
        const textMetrics = ctx.measureText(labelText)
        ctx.fillStyle = 'rgba(255, 255, 255, 0.9)'
        ctx.fillRect(previewX + 5, 5, textMetrics.width + 6, 16)
        ctx.fillStyle = '#000'
        ctx.fillText(labelText, previewX + 8, 17)
      } else {
        // Creating new annotation
        const previewDuration = Math.abs(currentTime - dragStart.time)
        const previewStart = Math.min(dragStart.time, currentTime)
        const startXCanvas = (previewStart - viewportStart) * pixelsPerSecond
        const widthCanvas = previewDuration * pixelsPerSecond

        ctx.fillStyle = 'rgba(33, 150, 243, 0.4)'
        ctx.fillRect(startXCanvas, 0, widthCanvas, canvas.height)
        
        ctx.font = 'bold 12px Arial'
        const labelText = `${selectedDescription} (${previewDuration.toFixed(2)}s)`
        const textMetrics = ctx.measureText(labelText)
        ctx.fillStyle = 'rgba(255, 255, 255, 0.9)'
        ctx.fillRect(startXCanvas + 5, 5, textMetrics.width + 6, 16)
        ctx.fillStyle = '#000'
        ctx.fillText(labelText, startXCanvas + 8, 17)
      }
    })
  }

  const handleMouseUp = async (e) => {
    if (!isDragging || !dragStart) return

    // Cancel any pending animation frame
    if (rafIdRef.current) {
      cancelAnimationFrame(rafIdRef.current)
      rafIdRef.current = null
    }

    const canvas = canvasRef.current
    const rect = canvas.getBoundingClientRect()
    const endX = e.clientX - rect.left
    const endTime = viewportStart + (endX / rect.width) * viewportDuration

    if (editingAnnotation && dragMode) {
      // Update existing annotation
      let newOnset = editingAnnotation.onset
      let newDuration = editingAnnotation.duration

      if (dragMode === 'left') {
        newOnset = endTime
        newDuration = (editingAnnotation.onset + editingAnnotation.duration) - newOnset
      } else if (dragMode === 'right') {
        newDuration = endTime - editingAnnotation.onset
      } else if (dragMode === 'move') {
        const timeDelta = endTime - dragStart.time
        newOnset = editingAnnotation.onset + timeDelta
      }

      // Clear dragging state immediately for instant visual feedback
      setIsDragging(false)
      setDragStart(null)
      setDragMode(null)
      setEditingAnnotation(null)
      setSelectedAnnotation(null)
      
      if (newDuration > 0.1 && (Math.abs(newOnset - editingAnnotation.onset) > 0.01 || Math.abs(newDuration - editingAnnotation.duration) > 0.01)) {
        // Save updated annotation in background (don't await)
        axios.put(
          `${API_URL}/api/annotations/${editingAnnotation.id}?dataset_id=${dataset.id}`,
          {
            onset: newOnset,
            duration: newDuration,
            description: editingAnnotation.description
          }
        ).then((response) => {
          // Emit socket event to notify other users
          if (socket && socket.connected) {
            socket.emit('annotation_updated', {
              ...response.data,
              dataset_id: dataset.id,
              user: currentUser
            })
          }
          
          // Refresh annotations from parent after successful save
          if (onAnnotationsRefresh) {
            onAnnotationsRefresh()
          }
        }).catch((error) => {
          console.error('Error updating annotation:', error)
          alert('Error updating annotation: ' + (error.response?.data?.detail || error.message))
          // Refresh to revert to server state
          if (onAnnotationsRefresh) {
            onAnnotationsRefresh()
          }
        })
      }
    } else {
      // Creating new annotation
      const onset = Math.min(dragStart.time, endTime)
      const duration = Math.abs(endTime - dragStart.time)

      // Clear dragging state immediately
      setIsDragging(false)
      setDragStart(null)
      setDragMode(null)
      setEditingAnnotation(null)

      if (duration > 0.1) {
        onAnnotationCreate?.({ 
          onset, 
          duration,
          description: selectedDescription
        })
      }
    }

    renderCanvas()
  }

  const panLeft = () => {
    if (loading || !dataset) return  // Prevent multiple clicks while loading
    const newStart = Math.max(0, viewportStart - viewportDuration * 0.5)
    console.log('Pan left: from', viewportStart, 'to', newStart)
    setViewportStart(newStart)
  }

  const panRight = () => {
    if (loading || !dataset) return  // Prevent multiple clicks while loading
    const maxStart = Math.max(0, (dataset.duration || 0) - viewportDuration)
    const newStart = Math.min(maxStart, viewportStart + viewportDuration * 0.5)
    console.log('Pan right: from', viewportStart, 'to', newStart, 'max:', maxStart)
    setViewportStart(newStart)
  }

  const zoomIn = () => {
    if (!dataset || !isFinite(viewportDuration)) return
    const newDuration = Math.max(0.5, viewportDuration / 1.5)
    setViewportDuration(newDuration)
    // Adjust viewport start if needed to stay in bounds
    if (viewportStart + newDuration > dataset.duration) {
      setViewportStart(Math.max(0, dataset.duration - newDuration))
    }
  }

  const zoomOut = () => {
    if (!dataset || !isFinite(viewportDuration)) return
    
    // Use a large default if dataset.duration is not available
    const maxDuration = isFinite(dataset.duration) ? dataset.duration : 3600
    const newDuration = Math.min(maxDuration, viewportDuration * 1.5)
    setViewportDuration(newDuration)
    
    // Adjust viewport start if needed to stay in bounds
    if (isFinite(dataset.duration) && viewportStart + newDuration > dataset.duration) {
      setViewportStart(Math.max(0, dataset.duration - newDuration))
    }
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
  
  // Debounced slider handler to prevent excessive API calls
  const handleSliderChange = useCallback((e) => {
    const newValue = parseFloat(e.target.value)
    
    // Update display immediately for responsive feel
    lastViewportStartRef.current = newValue
    
    // Clear existing debounce timer
    if (debounceTimerRef.current) {
      clearTimeout(debounceTimerRef.current)
    }
    
    // Set new debounce timer (300ms delay)
    debounceTimerRef.current = setTimeout(() => {
      setViewportStart(newValue)
    }, 300)
  }, [])
  
  // Sync ref with state (for button clicks and completed debounce)
  useEffect(() => {
    lastViewportStartRef.current = viewportStart
  }, [viewportStart])
  
  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (debounceTimerRef.current) {
        clearTimeout(debounceTimerRef.current)
      }
      if (rafIdRef.current) {
        cancelAnimationFrame(rafIdRef.current)
      }
    }
  }, [])
  
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
      {dataset && signalData && (() => {
        const effectiveDuration = dataset.duration || dataset.metadata?.duration || 3600
        const maxSlider = Math.max(1, effectiveDuration - viewportDuration)
        const isDisabled = !effectiveDuration || effectiveDuration <= viewportDuration
        
        console.log('Slider state:', { 
          duration: dataset.duration, 
          metaDuration: dataset.metadata?.duration,
          effectiveDuration, 
          maxSlider, 
          isDisabled,
          viewportDuration 
        })
        
        return (
          <div style={{ marginBottom: '10px' }}>
            <label style={{ fontSize: '12px', fontWeight: 'bold', marginBottom: '5px', display: 'block' }}>
              Time Navigation: {lastViewportStartRef.current.toFixed(1)}s / {effectiveDuration?.toFixed(1) || '?'}s
            </label>
            <input
              type="range"
              min="0"
              max={maxSlider}
              step="0.1"
              value={lastViewportStartRef.current}
              onChange={handleSliderChange}
              onInput={(e) => {
                // Update ref immediately for smooth visual feedback
                lastViewportStartRef.current = parseFloat(e.target.value)
                // Force re-render of label only (not canvas)
                e.target.previousElementSibling.textContent = 
                  `Time Navigation: ${lastViewportStartRef.current.toFixed(1)}s / ${effectiveDuration?.toFixed(1) || '?'}s`
              }}
              style={{ width: '100%', cursor: isDisabled ? 'not-allowed' : 'pointer' }}
              disabled={isDisabled}
            />
          </div>
        )
      })()}

      <div className="canvas-container" style={{ maxHeight: '600px', overflowY: 'auto', overflowX: 'hidden' }}>
        <canvas
          ref={canvasRef}
          width={1200}
          height={600}
          onMouseDown={handleMouseDown}
          onMouseMove={(e) => {
            handleMouseHover(e)
            handleMouseMove(e)
          }}
          onMouseUp={handleMouseUp}
          onMouseLeave={handleMouseUp}
          style={{ display: 'block' }}
        />
      </div>

      <div className="viewer-instructions">
        💡 <strong>Tip:</strong> Click and drag to create a "{selectedDescription}" annotation. Click an annotation to select it, then drag edges to resize or middle to move. Scroll vertically to see all channels.
      </div>
    </div>
  )
}

export default SignalViewer
