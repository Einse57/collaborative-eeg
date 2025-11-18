import { useState, useEffect } from 'react'
import axios from 'axios'
import './DatasetManager.css'

// API URL from environment variable, fallback to localhost
const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

function DatasetManager({ datasets, selectedDataset, onDatasetSelect, onUploadSuccess, onLoadDatasets, onAnnotationsRefresh }) {
  const [uploading, setUploading] = useState(false)
  const [loadingSample, setLoadingSample] = useState(false)
  const [detectingEvents, setDetectingEvents] = useState(false)
  const [detectionMethod, setDetectionMethod] = useState(null)
  const [detectionPlugins, setDetectionPlugins] = useState([])
  const [pluginsLoading, setPluginsLoading] = useState(true)

  // Load available detection plugins on mount
  useEffect(() => {
    loadDetectionPlugins()
  }, [])

  const loadDetectionPlugins = async () => {
    try {
      console.log('Loading detection plugins from:', `${API_URL}/api/detection/plugins`)
      const response = await axios.get(`${API_URL}/api/detection/plugins`)
      console.log('Plugins response:', response.data)
      const availablePlugins = response.data.plugins.filter(p => p.available)
      console.log('Available plugins:', availablePlugins)
      setDetectionPlugins(availablePlugins)
      setPluginsLoading(false)
    } catch (error) {
      console.error('Error loading detection plugins:', error)
      console.error('Error details:', error.response?.data || error.message)
      setDetectionPlugins([])
      setPluginsLoading(false)
    }
  }

  const handleFileUpload = async (event) => {
    const file = event.target.files[0]
    if (!file) return

    const formData = new FormData()
    formData.append('file', file)

    setUploading(true)
    try {
      await axios.post(`${API_URL}/api/datasets/upload`, formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
      })
      // No alert - dataset will appear in the list visually
      onUploadSuccess()
    } catch (error) {
      alert('Error uploading dataset: ' + error.message)
    } finally {
      setUploading(false)
    }
  }

  const handleLoadSample = async (sampleName) => {
    setLoadingSample(true)
    try {
      await axios.post(`${API_URL}/api/datasets/samples/${sampleName}`)
      // No alert - dataset will appear in the list visually
      onLoadDatasets()
    } catch (error) {
      alert('Error loading sample dataset: ' + error.message)
    } finally {
      setLoadingSample(false)
    }
  }

  const handleDetectEvents = async (pluginId) => {
    if (!selectedDataset) {
      alert('Please select a dataset first!')
      return
    }

    setDetectingEvents(true)
    setDetectionMethod(pluginId)
    
    try {
      const response = await axios.post(
        `${API_URL}/api/detection/${selectedDataset.id}/detect`,
        {
          plugin_id: pluginId,
          segment_duration: 2.0,
          threshold: 0.5
        }
      )
      
      const { data } = response
      alert(`${data.message}\n\nPlugin: ${data.plugin_name}\nDetections: ${data.detections.length}`)
      
      // Reload annotations to show detected events
      if (onAnnotationsRefresh) {
        onAnnotationsRefresh()
      }
    } catch (error) {
      const errorMsg = error.response?.data?.detail || error.message
      alert(`Error detecting events: ${errorMsg}`)
    } finally {
      setDetectingEvents(false)
      setDetectionMethod(null)
    }
  }



  const handleDeleteDataset = async (dataset, event) => {
    event.stopPropagation() // Prevent triggering dataset selection
    
    if (!confirm(`Are you sure you want to remove "${dataset.filename}"?`)) {
      return
    }

    try {
      await axios.delete(`${API_URL}/api/datasets/${dataset.id}`)
      onLoadDatasets() // Reload the dataset list
      
      // If the deleted dataset was selected, clear selection
      if (selectedDataset?.id === dataset.id) {
        onDatasetSelect(null)
      }
    } catch (error) {
      alert('Error removing dataset: ' + error.message)
    }
  }

  return (
    <div className="dataset-manager">
      <h2>📂 Datasets</h2>
      
      <div className="upload-section">
        <label htmlFor="file-upload" className="upload-btn primary-btn">
          {uploading ? '⏳ Uploading...' : '📤 Upload File'}
        </label>
        <input
          id="file-upload"
          type="file"
          accept=".fif,.edf,.bdf,.set,.vhdr"
          onChange={handleFileUpload}
          disabled={uploading}
          style={{ display: 'none' }}
        />
      </div>

      <div className="sample-section">
        <h3>Sample Datasets</h3>
        <button
          className="sample-btn secondary-btn"
          onClick={() => handleLoadSample('testing')}
          disabled={loadingSample}
        >
          {loadingSample ? '⏳ Loading...' : '🔬 Download from MNE'}
        </button>
      </div>

      <div className="event-detection-section">
        <h3>🧠 Event Detection</h3>
        <p className="warning-message" style={{fontSize: '0.7rem', color: '#d32f2f', marginBottom: '0.5rem'}}>
          ⚠️ Research Use Only
        </p>
        
        {pluginsLoading ? (
          <p className="hint-message">⏳ Loading detection plugins...</p>
        ) : detectionPlugins.length === 0 ? (
          <p className="hint-message" style={{color: '#999'}}>
            No detection plugins loaded
          </p>
        ) : (
          <>
            <div className="detection-buttons">
              {detectionPlugins.map(plugin => (
                <button
                  key={plugin.id}
                  className="detection-btn"
                  style={{
                    background: plugin.color,
                    opacity: (detectingEvents || !selectedDataset) ? 0.5 : 1
                  }}
                  onClick={() => handleDetectEvents(plugin.id)}
                  disabled={detectingEvents || !selectedDataset}
                  title={plugin.description}
                >
                  {detectingEvents && detectionMethod === plugin.id 
                    ? '⏳ Detecting...' 
                    : `${plugin.icon} ${plugin.name}`}
                </button>
              ))}
            </div>
            {!selectedDataset && (
              <p className="hint-message">Select a dataset above to enable detection</p>
            )}
          </>
        )}
      </div>

      <div className="dataset-list">
        <h3>Your Datasets ({datasets.length})</h3>
        {datasets.length === 0 ? (
          <p className="empty-message">No datasets yet. Upload one to start!</p>
        ) : (
          datasets.map(dataset => (
            <div
              key={dataset.id}
              className={`dataset-item ${selectedDataset?.id === dataset.id ? 'selected' : ''}`}
              onClick={() => onDatasetSelect(dataset)}
            >
              <div className="dataset-header">
                <div className="dataset-name">{dataset.filename}</div>
                <button
                  className="delete-dataset-btn"
                  onClick={(e) => handleDeleteDataset(dataset, e)}
                  title="Remove dataset"
                >
                  ✕
                </button>
              </div>
              <div className="dataset-info">
                <span>📊 {dataset.n_channels} channels</span>
                <span>⏱️ {dataset.duration.toFixed(1)}s</span>
                <span>🔄 {dataset.sampling_rate}Hz</span>
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  )
}

export default DatasetManager
