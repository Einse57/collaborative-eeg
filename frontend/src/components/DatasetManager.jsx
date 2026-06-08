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

  // H5 browser state
  const [h5BrowseOpen, setH5BrowseOpen] = useState(false)
  const [h5Path, setH5Path] = useState('')
  const [h5Entries, setH5Entries] = useState([])
  const [h5Browsing, setH5Browsing] = useState(false)
  const [h5Inspecting, setH5Inspecting] = useState(null)  // inspection result
  const [h5Loading, setH5Loading] = useState(false)
  const [h5SegStart, setH5SegStart] = useState(0)
  const [h5SegDuration, setH5SegDuration] = useState('')  // '' = full file
  const [h5PathHistory, setH5PathHistory] = useState([])

  // Load available detection plugins on mount.
  // Backend loads plugins in background — poll until ready.
  useEffect(() => {
    let cancelled = false
    const poll = async () => {
      const POLL_INTERVAL = 3000
      const MAX_POLLS = 60  // up to ~3 minutes
      for (let i = 0; i < MAX_POLLS && !cancelled; i++) {
        try {
          const response = await axios.get(`${API_URL}/api/detection/plugins`)
          if (cancelled) return
          const data = response.data
          const availablePlugins = data.plugins.filter(p => p.available)

          // Update plugins found so far (they register incrementally)
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
          setPluginConfigs(prev => ({ ...prev, ...defaults }))

          // If backend is done loading, stop polling
          if (data.loaded) {
            setPluginsLoading(false)
            console.log('All plugins loaded:', availablePlugins.length, 'available')
            return
          }
          // Still loading — show what we have so far
          console.log(`Plugins still loading... ${availablePlugins.length} available so far`)
        } catch (error) {
          console.warn('Plugin poll failed:', error.message)
        }
        if (!cancelled) {
          await new Promise(r => setTimeout(r, POLL_INTERVAL))
        }
      }
      if (!cancelled) {
        console.warn('Plugin loading poll timed out')
        setPluginsLoading(false)
      }
    }
    poll()
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

  // ── H5 browser handlers ──────────────────────────────────────────────
  const browseH5 = async (dir) => {
    setH5Browsing(true)
    try {
      const params = dir ? { path: dir } : {}
      const resp = await axios.get(`${API_URL}/api/datasets/h5/browse`, { params })
      setH5Entries(resp.data.entries)
      setH5Path(resp.data.path)
      setH5Inspecting(null)
    } catch (error) {
      alert('Error browsing H5 directory: ' + (error.response?.data?.detail || error.message))
    } finally {
      setH5Browsing(false)
    }
  }

  const openH5Browser = () => {
    setH5BrowseOpen(true)
    setH5PathHistory([])
    // Browse with no path — server returns its default root
    browseH5(h5Path || '')
  }

  const navigateH5 = (dir) => {
    setH5PathHistory(prev => [...prev, h5Path])
    browseH5(dir)
  }

  const navigateH5Up = () => {
    if (h5PathHistory.length > 0) {
      const prev = h5PathHistory[h5PathHistory.length - 1]
      setH5PathHistory(h => h.slice(0, -1))
      browseH5(prev)
    }
  }

  const inspectH5 = async (filePath) => {
    setH5Inspecting({ loading: true, path: filePath })
    try {
      const resp = await axios.get(`${API_URL}/api/datasets/h5/inspect`, {
        params: { path: filePath },
      })
      setH5Inspecting(resp.data)
      setH5SegStart(0)
      setH5SegDuration('')
    } catch (error) {
      alert('Error inspecting H5: ' + (error.response?.data?.detail || error.message))
      setH5Inspecting(null)
    }
  }

  const loadH5 = async () => {
    if (!h5Inspecting || h5Inspecting.loading) return
    const body = {
      path: h5Inspecting.path,
      start_sec: h5SegStart,
    }
    if (h5SegDuration !== '' && h5SegDuration > 0) {
      body.duration_sec = parseFloat(h5SegDuration)
    }

    // Warn if loading >2 GB into memory
    const estMem = h5Inspecting.estimated_memory_gb
    if (!body.duration_sec && estMem > 2) {
      if (!confirm(
        `This will load ~${estMem.toFixed(1)} GB into memory (${h5Inspecting.n_channels} ch × ${h5Inspecting.duration_hours.toFixed(1)} hours).\n\nContinue, or cancel and set a segment duration?`
      )) return
    }

    setH5Loading(true)
    try {
      const resp = await axios.post(`${API_URL}/api/datasets/h5/load`, body)
      setH5BrowseOpen(false)
      setH5Inspecting(null)
      onUploadSuccess()
    } catch (error) {
      alert('Error loading H5: ' + (error.response?.data?.detail || error.message))
    } finally {
      setH5Loading(false)
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
        <button
          className="upload-btn primary-btn"
          style={{ marginTop: '0.5rem', background: '#0097a7' }}
          onClick={openH5Browser}
        >
          🗄️ Browse H5 Files
        </button>
      </div>

      {/* ── H5 File Browser Modal ─────────────────────────────────────── */}
      {h5BrowseOpen && (
        <div className="h5-overlay" onClick={() => setH5BrowseOpen(false)}>
          <div className="h5-modal" onClick={e => e.stopPropagation()}>
            <div className="h5-modal-header">
              <h3>🗄️ H5 File Browser</h3>
              <button className="h5-close-btn" onClick={() => setH5BrowseOpen(false)}>✕</button>
            </div>

            {/* Breadcrumb / path */}
            <div className="h5-path-bar">
              {h5PathHistory.length > 0 && (
                <button className="h5-nav-btn" onClick={navigateH5Up}>⬆ Back</button>
              )}
              <span className="h5-path-text" title={h5Path}>{h5Path}</span>
            </div>

            {/* File list */}
            <div className="h5-file-list">
              {h5Browsing ? (
                <p style={{textAlign:'center',color:'#888',padding:'2rem'}}>Loading…</p>
              ) : h5Entries.length === 0 ? (
                <p style={{textAlign:'center',color:'#888',padding:'2rem'}}>No H5 files or folders found</p>
              ) : (
                h5Entries.map(entry => (
                  <div
                    key={entry.path}
                    className={`h5-entry ${h5Inspecting?.path === entry.path ? 'selected' : ''}`}
                    onClick={() => entry.type === 'directory' ? navigateH5(entry.path) : inspectH5(entry.path)}
                  >
                    <span className="h5-entry-icon">{entry.type === 'directory' ? '📁' : '📄'}</span>
                    <span className="h5-entry-name">{entry.name}</span>
                    {entry.type === 'directory' && entry.h5_count > 0 && (
                      <span className="h5-entry-badge">{entry.h5_count} h5</span>
                    )}
                    {entry.type === 'file' && (
                      <span className="h5-entry-size">{entry.size_mb >= 1024 ? `${(entry.size_mb/1024).toFixed(1)} GB` : `${entry.size_mb.toFixed(0)} MB`}</span>
                    )}
                  </div>
                ))
              )}
            </div>

            {/* Inspection panel */}
            {h5Inspecting && !h5Inspecting.loading && (
              <div className="h5-inspect-panel">
                <h4>📋 {h5Inspecting.patient_id} — File Info</h4>
                <div className="h5-inspect-grid">
                  <span>Channels:</span><span>{h5Inspecting.n_channels}</span>
                  <span>Duration:</span><span>{h5Inspecting.duration_hours.toFixed(1)} hours ({(h5Inspecting.duration_seconds).toFixed(0)}s)</span>
                  <span>Sample Rate:</span><span>{h5Inspecting.fs} Hz</span>
                  <span>File Size:</span><span>{h5Inspecting.size_gb.toFixed(2)} GB</span>
                  <span>Seizures:</span><span>{h5Inspecting.n_seizures}</span>
                  <span>Est. Memory:</span>
                  <span style={{color: h5Inspecting.estimated_memory_gb > 2 ? '#f44336' : '#4caf50', fontWeight: 600}}>
                    {h5Inspecting.estimated_memory_gb.toFixed(2)} GB
                  </span>
                  {h5Inspecting.is_vds_broken && (
                    <>
                      <span>VDS:</span>
                      <span style={{color:'#ff9800'}}>⚠ Broken — will read from {h5Inspecting.part_files.length} parts</span>
                    </>
                  )}
                </div>

                {h5Inspecting.n_seizures > 0 && (
                  <details style={{marginTop:'0.5rem',fontSize:'0.8rem'}}>
                    <summary style={{cursor:'pointer',color:'#1976d2'}}>View seizure times</summary>
                    <ul style={{margin:'0.25rem 0',paddingLeft:'1.25rem'}}>
                      {h5Inspecting.seizures.map((sz, i) => (
                        <li key={i}>Sz{i+1}: {sz.onset.toFixed(1)}s – {sz.offset.toFixed(1)}s ({(sz.offset - sz.onset).toFixed(1)}s)</li>
                      ))}
                    </ul>
                  </details>
                )}

                {/* Segment controls */}
                <div className="h5-segment-controls">
                  <label>
                    Start (sec):
                    <input
                      type="number"
                      min="0"
                      max={h5Inspecting.duration_seconds}
                      value={h5SegStart}
                      onChange={e => setH5SegStart(parseFloat(e.target.value) || 0)}
                      className="h5-seg-input"
                    />
                  </label>
                  <label>
                    Duration (sec):
                    <input
                      type="number"
                      min="0"
                      max={h5Inspecting.duration_seconds - h5SegStart}
                      placeholder="entire file"
                      value={h5SegDuration}
                      onChange={e => setH5SegDuration(e.target.value)}
                      className="h5-seg-input"
                    />
                  </label>
                </div>

                <button
                  className="h5-load-btn"
                  onClick={loadH5}
                  disabled={h5Loading}
                >
                  {h5Loading ? '⏳ Loading…' : `📥 Load ${h5SegDuration ? `${h5SegDuration}s segment` : 'entire file'}`}
                </button>
              </div>
            )}
            {h5Inspecting?.loading && (
              <div className="h5-inspect-panel" style={{textAlign:'center',color:'#888'}}>
                ⏳ Inspecting file…
              </div>
            )}
          </div>
        </div>
      )}

      <div className="event-detection-section">
        <h3>🧠 Event Detection</h3>
        <p className="warning-message" style={{fontSize: '0.7rem', color: '#d32f2f', marginBottom: '0.5rem'}}>
          ⚠️ Research Use Only
        </p>
        
        {pluginsLoading && detectionPlugins.length === 0 ? (
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
            {pluginsLoading && (
              <p className="hint-message" style={{color: '#888', fontSize: '0.7rem'}}>
                ⏳ Loading more plugins...
              </p>
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
