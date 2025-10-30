import { useState } from 'react'
import axios from 'axios'
import './DatasetManager.css'

// API URL from environment variable, fallback to localhost
const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

function DatasetManager({ datasets, selectedDataset, onDatasetSelect, onUploadSuccess, onLoadDatasets }) {
  const [uploading, setUploading] = useState(false)
  const [loadingSample, setLoadingSample] = useState(false)

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
      alert('Dataset uploaded successfully!')
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
      alert(`Sample dataset "${sampleName}" loaded successfully!`)
      onLoadDatasets()
    } catch (error) {
      alert('Error loading sample dataset: ' + error.message)
    } finally {
      setLoadingSample(false)
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
          {loadingSample ? '⏳ Loading...' : '🔬 Load Sample (Testing)'}
        </button>
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
              <div className="dataset-name">{dataset.filename}</div>
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
