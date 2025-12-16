import { useState } from 'react'
import axios from 'axios'
import './AnnotationPanel.css'

// API URL from environment variable, fallback to localhost
// API URL detection:
// - If accessed through nginx (port 80 or 443), use relative paths
// - If accessed directly (port 3000), use localhost:8000
// - Can be overridden with VITE_API_URL environment variable
const getApiUrl = () => {
  if (import.meta.env.VITE_API_URL) {
    return import.meta.env.VITE_API_URL;
  }
  const port = window.location.port;
  if (port === '' || port === '80' || port === '443') {
    return window.location.origin;
  }
  return 'http://localhost:8000';
};

const API_URL = getApiUrl();

function AnnotationPanel({ datasetId, selectedDataset, annotations, customAnnotationTypes, onCustomTypesChange, onAnnotationsChange, socket }) {
  const [filter, setFilter] = useState('')
  const [customTypeName, setCustomTypeName] = useState('')
  
  // Check if the dataset is an EDF file (for conditional Export EDF+ button)
  const isEDFFile = selectedDataset?.filename?.toLowerCase().endsWith('.edf')

  // Common annotation types
  const baseAnnotationTypes = [
    'BAD_artifact',
    'BAD_blink', 
    'BAD_movement',
    'Blink',
    'Movement',
    'Sleep_spindle',
    'K_complex'
  ]
  
  // Combine base types with custom types
  const allAnnotationTypes = [...baseAnnotationTypes, ...customAnnotationTypes]

  const handleAddCustomType = (e) => {
    e.preventDefault()
    
    if (!customTypeName.trim()) {
      alert('Please enter a custom type name')
      return
    }
    
    // Check if already exists
    if (allAnnotationTypes.includes(customTypeName.trim())) {
      alert('This annotation type already exists')
      return
    }
    
    // Add to custom types via parent component
    onCustomTypesChange([...customAnnotationTypes, customTypeName.trim()])
    setCustomTypeName('')
    alert(`Custom type "${customTypeName.trim()}" added! You can now select it from the dropdown in the Signal Viewer.`)
  }

  const handleDeleteAnnotation = async (annotationId) => {
    if (!confirm('Delete this annotation?')) return

    try {
      await axios.delete(
        `${API_URL}/api/annotations/${annotationId}?dataset_id=${datasetId}`
      )

      // Broadcast to other users
      if (socket) {
        socket.emit('annotation_deleted', {
          dataset_id: datasetId,
          annotation_id: annotationId
        })
      }

      onAnnotationsChange()
    } catch (error) {
      alert('Error deleting annotation: ' + error.message)
    }
  }

  const handleExport = async (format) => {
    try {
      const response = await axios.get(
        `${API_URL}/api/annotations/${datasetId}/export?format=${format}`
      )

      if (format === 'json') {
        const blob = new Blob([JSON.stringify(response.data.annotations, null, 2)], 
          { type: 'application/json' })
        const url = URL.createObjectURL(blob)
        const a = document.createElement('a')
        a.href = url
        a.download = `annotations_${datasetId}.json`
        a.click()
        URL.revokeObjectURL(url)
      } else if (format === 'csv') {
        const blob = new Blob([response.data.data], { type: 'text/csv' })
        const url = URL.createObjectURL(blob)
        const a = document.createElement('a')
        a.href = url
        a.download = `annotations_${datasetId}.csv`
        a.click()
        URL.revokeObjectURL(url)
      }
    } catch (error) {
      alert('Error exporting annotations: ' + error.message)
    }
  }

  const handleExportEDFPlus = async () => {
    try {
      const response = await axios.get(
        `${API_URL}/api/datasets/${datasetId}/export/edfplus`,
        { responseType: 'blob' }
      )
      
      // Create a download link
      const url = window.URL.createObjectURL(new Blob([response.data]))
      const link = document.createElement('a')
      link.href = url
      link.setAttribute('download', `dataset_${datasetId}_with_annotations.edf`)
      document.body.appendChild(link)
      link.click()
      link.remove()
      window.URL.revokeObjectURL(url)
      
      alert('Successfully exported dataset with annotations to EDF+ format!')
    } catch (error) {
      const errorMsg = error.response?.data?.detail || error.message
      alert(`Error exporting to EDF+: ${errorMsg}`)
    }
  }

  const handleImport = async (event) => {
    const file = event.target.files?.[0]
    if (!file) return

    try {
      const text = await file.text()
      let annotationsToImport = []

      if (file.name.endsWith('.json')) {
        const data = JSON.parse(text)
        // Handle both array format and object with annotations key
        annotationsToImport = Array.isArray(data) ? data : data.annotations || []
      } else if (file.name.endsWith('.csv')) {
        // Parse CSV
        const lines = text.split('\n').filter(line => line.trim())
        const headers = lines[0].split(',')
        
        for (let i = 1; i < lines.length; i++) {
          const values = lines[i].split(',')
          annotationsToImport.push({
            onset: parseFloat(values[0]),
            duration: parseFloat(values[1]),
            description: values[2]?.trim() || 'Imported'
          })
        }
      } else {
        alert('Please select a JSON or CSV file')
        return
      }

      // Collect unique annotation types from imported data
      const newTypes = new Set()
      for (const ann of annotationsToImport) {
        const desc = ann.description?.trim()
        if (desc && !allAnnotationTypes.includes(desc)) {
          newTypes.add(desc)
        }
      }

      // Add new types to custom types
      if (newTypes.size > 0) {
        const updatedCustomTypes = [...customAnnotationTypes, ...Array.from(newTypes)]
        onCustomTypesChange(updatedCustomTypes)
        console.log('Added new annotation types from import:', Array.from(newTypes))
      }

      // Import each annotation
      let successCount = 0
      for (const ann of annotationsToImport) {
        try {
          const response = await axios.post(`${API_URL}/api/annotations/`, {
            dataset_id: datasetId,
            onset: ann.onset,
            duration: ann.duration,
            description: ann.description,
            user: 'imported'
          })
          
          // Broadcast to other users
          if (socket) {
            socket.emit('annotation_created', {
              dataset_id: datasetId,
              annotation: response.data
            })
          }
          
          successCount++
        } catch (error) {
          console.error('Error importing annotation:', error)
        }
      }

      const newTypesMsg = newTypes.size > 0 
        ? `\n\nNew annotation types added: ${Array.from(newTypes).join(', ')}`
        : ''
      
      alert(`Successfully imported ${successCount} of ${annotationsToImport.length} annotations${newTypesMsg}`)
      onAnnotationsChange()
      
      // Clear file input
      event.target.value = ''
    } catch (error) {
      alert('Error importing annotations: ' + error.message)
    }
  }

  const formatTime = (seconds) => {
    const mins = Math.floor(seconds / 60)
    const secs = (seconds % 60).toFixed(2)
    return `${mins}:${secs.padStart(5, '0')}`
  }

  const getAnnotationColor = (description) => {
    if (description.startsWith('BAD')) return '#f44336'
    if (description === 'Blink') return '#4caf50'
    return '#ff9800'
  }

  const isEventDetection = (user) => {
    return user === 'EventDetector_RF' || user === 'EventDetector_CNN' ||
           user === 'SeizureDetector_RF' || user === 'SeizureDetector_CNN'  // backwards compatibility
  }

  const getDetectionMethodLabel = (user) => {
    if (user === 'EventDetector_RF' || user === 'SeizureDetector_RF') return '🌲 RF'
    if (user === 'EventDetector_CNN' || user === 'SeizureDetector_CNN') return '🔷 CNN'
    return ''
  }

  const getDetectionMethodColor = (user) => {
    if (user === 'EventDetector_RF' || user === 'SeizureDetector_RF') return '#2e7d32'
    if (user === 'EventDetector_CNN' || user === 'SeizureDetector_CNN') return '#1565c0'
    return '#666'
  }

  const filteredAnnotations = annotations.filter(ann =>
    ann.description.toLowerCase().includes(filter.toLowerCase())
  )

  return (
    <div className="annotation-panel card">
      <div className="panel-header">
        <h2>✏️ Annotations ({annotations.length})</h2>
        <div className="export-buttons">
          <label className="secondary-btn" style={{cursor: 'pointer', margin: 0}}>
            📁 Import
            <input 
              type="file" 
              accept=".json,.csv" 
              onChange={handleImport}
              style={{display: 'none'}}
            />
          </label>
          <button 
            className="secondary-btn"
            onClick={() => handleExport('json')}
          >
            💾 Export JSON
          </button>
          <button 
            className="secondary-btn"
            onClick={() => handleExport('csv')}
          >
            📄 Export CSV
          </button>
          {!isEDFFile && (
            <button 
              className="secondary-btn"
              onClick={handleExportEDFPlus}
              title="Export dataset with all annotations to EDF+ format"
            >
              📥 Export EDF+
            </button>
          )}
        </div>
      </div>

      <form className="annotation-form" onSubmit={handleAddCustomType} style={{marginBottom: '20px', borderBottom: '2px solid #e0e0e0', paddingBottom: '15px'}}>
        <h3>➕ Add Custom Annotation Type</h3>
        <div className="form-row">
          <input
            type="text"
            placeholder="e.g., Event, Artifact_noise, etc."
            value={customTypeName}
            onChange={(e) => setCustomTypeName(e.target.value)}
            style={{flex: 1}}
          />
          <button type="submit" className="primary-btn">Add Type</button>
        </div>
        {customAnnotationTypes.length > 0 && (
          <div style={{marginTop: '10px', fontSize: '12px', color: '#666'}}>
            Custom types: {customAnnotationTypes.join(', ')}
          </div>
        )}
      </form>

      <div className="annotation-filter">
        <input
          type="text"
          placeholder="🔍 Filter annotations..."
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
        />
      </div>

      <div className="annotation-list">
        {filteredAnnotations.length === 0 ? (
          <p className="empty-message">
            {filter ? 'No annotations match your filter' : 'No annotations yet. Draw on the canvas to create annotations!'}
          </p>
        ) : (
          <table>
            <thead>
              <tr>
                <th>Time</th>
                <th>Duration</th>
                <th>Description</th>
                <th>User/Method</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {filteredAnnotations.map(ann => (
                <tr key={ann.id} className={isEventDetection(ann.user) ? 'auto-detected' : ''}>
                  <td>{formatTime(ann.onset)}</td>
                  <td>{ann.duration.toFixed(2)}s</td>
                  <td>
                    <span 
                      className="annotation-badge"
                      style={{ backgroundColor: getAnnotationColor(ann.description) }}
                    >
                      {ann.description}
                    </span>
                    {isEventDetection(ann.user) && ann.confidence !== undefined && (
                      <div className="method-info" title={ann.method}>
                        Confidence: {(ann.confidence * 100).toFixed(1)}%
                      </div>
                    )}
                  </td>
                  <td>
                    {isEventDetection(ann.user) ? (
                      <span 
                        className="detection-badge"
                        style={{ 
                          backgroundColor: getDetectionMethodColor(ann.user),
                          color: 'white',
                          padding: '2px 8px',
                          borderRadius: '3px',
                          fontSize: '0.85em',
                          fontWeight: 'bold'
                        }}
                      >
                        {getDetectionMethodLabel(ann.user)}
                      </span>
                    ) : (
                      ann.user || 'Unknown'
                    )}
                  </td>
                  <td>
                    <button
                      className="danger-btn small-btn"
                      onClick={() => handleDeleteAnnotation(ann.id)}
                    >
                      🗑️
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  )
}

export default AnnotationPanel
