import { useState, useEffect } from 'react'
import axios from 'axios'
import './DatasetManager.css'

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

function DatasetManager({ datasets, selectedDataset, onDatasetSelect, onUploadSuccess, onLoadDatasets, onAnnotationsRefresh }) {
  const [uploading, setUploading] = useState(false)
  const [detectingEvents, setDetectingEvents] = useState(false)
  const [detectionMethod, setDetectionMethod] = useState(null)
  const [detectionPlugins, setDetectionPlugins] = useState([])
  const [pluginsLoading, setPluginsLoading] = useState(true)
  const [detectionProgress, setDetectionProgress] = useState({ pct: 0, message: '' })
  const [pluginConfigs, setPluginConfigs] = useState({})  // { pluginId: { key: value } }
  const [expandedPlugin, setExpandedPlugin] = useState(null)  // pluginId or null

  // Load available detection plugins on mount (retry if backend not ready yet)
  useEffect(() => {
    let cancelled = false
    const attempt = async (retries = 5, delay = 2000) => {
      for (let i = 0; i < retries && !cancelled; i++) {
        try {
          console.log(`Loading detection plugins (attempt ${i + 1}/${retries})…`)
          const response = await axios.get(`${API_URL}/api/detection/plugins`)
          if (cancelled) return
          const availablePlugins = response.data.plugins.filter(p => p.available)
          console.log('Available plugins:', availablePlugins)
          setDetectionPlugins(availablePlugins)
          // Initialize per-plugin config from schema defaults
          const defaults = {}
          for (const p of availablePlugins) {
            if (p.config_schema) {
              const cfg = {}
              for (const [key, schema] of Object.entries(p.config_schema)) {
                cfg[key] = schema.default
              }
              defaults[p.id] = cfg
            }
          }
          setPluginConfigs(defaults)
          setPluginsLoading(false)
          return
        } catch (error) {
          console.warn(`Plugin load attempt ${i + 1} failed:`, error.message)
          if (i < retries - 1 && !cancelled) {
            await new Promise(r => setTimeout(r, delay))
          }
        }
      }
      if (!cancelled) {
        console.error('Could not load detection plugins after retries')
        setDetectionPlugins([])
        setPluginsLoading(false)
      }
    }
    attempt()
    return () => { cancelled = true }
  }, [])

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

  const handleDetectEvents = async (pluginId) => {
    if (!selectedDataset) {
      alert('Please select a dataset first!')
      return
    }

    setDetectingEvents(true)
    setDetectionMethod(pluginId)
    
    try {
      // Start the detection job
      const cfg = pluginConfigs[pluginId] || {}
      const startResponse = await axios.post(
        `${API_URL}/api/detection/${selectedDataset.id}/detect`,
        {
          plugin_id: pluginId,
          segment_duration: cfg.segment_duration ?? 2.0,
          threshold: cfg.threshold ?? 0.5,
          config: cfg
        }
      )
      
      const jobId = startResponse.data.job_id

      // Poll until the job completes or fails
      let result = null
      setDetectionProgress({ pct: 0, message: 'Starting…' })
      while (true) {
        await new Promise(r => setTimeout(r, 1000))
        const pollResponse = await axios.get(`${API_URL}/api/detection/jobs/${jobId}`)
        const job = pollResponse.data

        setDetectionProgress({ pct: Math.round(job.progress || 0), message: job.message || '' })

        if (job.status === 'completed') {
          result = job
          break
        }
        if (job.status === 'failed') {
          throw new Error(job.error || job.message || 'Detection failed')
        }
      }

      alert(`${result.message}\n\nPlugin: ${result.plugin_name}\nDetections: ${result.detections.length}`)
      
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
      setDetectionProgress({ pct: 0, message: '' })
    }
  }

  const updatePluginConfig = (pluginId, key, value) => {
    setPluginConfigs(prev => ({
      ...prev,
      [pluginId]: { ...(prev[pluginId] || {}), [key]: value }
    }))
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
          accept=".fif,.edf,.bdf,.set,.vhdr,.mat"
          onChange={handleFileUpload}
          disabled={uploading}
          style={{ display: 'none' }}
        />
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
                <div key={plugin.id} style={{width: '100%'}}>
                  <div style={{display: 'flex', gap: '4px', marginBottom: expandedPlugin === plugin.id ? '0' : undefined}}>
                    <button
                      className="detection-btn"
                      style={{
                        background: plugin.color,
                        opacity: (detectingEvents || !selectedDataset) ? 0.5 : 1,
                        flex: 1,
                      }}
                      onClick={() => handleDetectEvents(plugin.id)}
                      disabled={detectingEvents || !selectedDataset}
                      title={plugin.description}
                    >
                      {detectingEvents && detectionMethod === plugin.id 
                        ? `⏳ ${detectionProgress.pct}%` 
                        : `${plugin.icon} ${plugin.name}`}
                    </button>
                    {plugin.config_schema && Object.keys(plugin.config_schema).length > 0 && (
                      <button
                        className="detection-btn"
                        style={{
                          background: expandedPlugin === plugin.id ? '#555' : '#888',
                          padding: '4px 8px',
                          minWidth: '32px',
                          flex: 'none',
                          fontSize: '0.75rem',
                        }}
                        onClick={() => setExpandedPlugin(expandedPlugin === plugin.id ? null : plugin.id)}
                        title="Configure plugin"
                      >
                        ⚙
                      </button>
                    )}
                  </div>
                  {expandedPlugin === plugin.id && plugin.config_schema && (
                    <div style={{
                      background: '#1e1e1e',
                      border: '1px solid #444',
                      borderRadius: '4px',
                      padding: '8px',
                      marginBottom: '4px',
                      fontSize: '0.75rem',
                    }}>
                      {Object.entries(plugin.config_schema).map(([key, schema]) => {
                        const val = pluginConfigs[plugin.id]?.[key] ?? schema.default
                        if (schema.type === 'number') {
                          return (
                            <div key={key} style={{marginBottom: '6px'}}>
                              <label style={{display: 'block', color: '#aaa', marginBottom: '2px'}}>
                                {schema.label || key}: <strong style={{color: '#fff'}}>{val}</strong>
                              </label>
                              <input
                                type="range"
                                min={schema.min ?? 0}
                                max={schema.max ?? 1}
                                step={schema.step ?? 0.01}
                                value={val}
                                onChange={(e) => updatePluginConfig(plugin.id, key, parseFloat(e.target.value))}
                                style={{width: '100%'}}
                              />
                            </div>
                          )
                        }
                        if (schema.type === 'string') {
                          return (
                            <div key={key} style={{marginBottom: '6px'}}>
                              <label style={{display: 'block', color: '#aaa', marginBottom: '2px'}}>
                                {schema.label || key}
                              </label>
                              <input
                                type="text"
                                value={val || ''}
                                onChange={(e) => updatePluginConfig(plugin.id, key, e.target.value)}
                                placeholder={schema.default || ''}
                                style={{
                                  width: '100%', padding: '3px 6px',
                                  background: '#2a2a2a', border: '1px solid #555',
                                  borderRadius: '3px', color: '#ddd', fontSize: '0.75rem',
                                }}
                              />
                            </div>
                          )
                        }
                        return null
                      })}
                    </div>
                  )}
                </div>
              ))}
            </div>
            {detectingEvents && detectionProgress.message && (
              <p className="hint-message" style={{color: '#1976d2', fontSize: '0.75rem'}}>
                {detectionProgress.message}
              </p>
            )}
            {!selectedDataset && !detectingEvents && (
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
