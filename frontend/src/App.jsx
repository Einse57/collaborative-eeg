import { useState, useEffect, useRef } from 'react'
import axios from 'axios'
import io from 'socket.io-client'
import DatasetManager from './components/DatasetManager'
import SignalViewer from './components/SignalViewer'
import AnnotationPanel from './components/AnnotationPanel'
import './App.css'

// API URL from environment variable, fallback to localhost
const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

function App() {
  const [datasets, setDatasets] = useState([])
  const [selectedDataset, setSelectedDataset] = useState(null)
  const [annotations, setAnnotations] = useState([])
  const [socket, setSocket] = useState(null)
  const [connectedUsers, setConnectedUsers] = useState([])
  const [customAnnotationTypes, setCustomAnnotationTypes] = useState([])  // Shared custom types
  const [currentUser, setCurrentUser] = useState(null)  // Current user name
  const selectedDatasetIdRef = useRef(null)  // Track selected dataset ID for socket events
  
  // Prompt for username on mount
  useEffect(() => {
    const username = localStorage.getItem('eeg_annotation_username')
    if (!username) {
      const newUsername = prompt('Enter your username:', `User${Math.floor(Math.random() * 1000)}`)
      if (newUsername && newUsername.trim()) {
        localStorage.setItem('eeg_annotation_username', newUsername.trim())
        setCurrentUser(newUsername.trim())
      } else {
        setCurrentUser(`User${Math.floor(Math.random() * 1000)}`)
      }
    } else {
      setCurrentUser(username)
    }
  }, [])

  const loadAnnotations = async (datasetId) => {
    try {
      console.log('Loading annotations for dataset:', datasetId)
      const response = await axios.get(`${API_URL}/api/annotations/${datasetId}`)
      console.log('Annotations loaded:', response.data.annotations.length)
      setAnnotations(response.data.annotations)
    } catch (error) {
      console.error('Error loading annotations:', error)
    }
  }

  // Initialize Socket.IO connection
  useEffect(() => {
    if (!currentUser) return
    
    const newSocket = io(API_URL)
    setSocket(newSocket)

    newSocket.on('connect', () => {
      console.log('Connected to server as', currentUser)
    })

    newSocket.on('annotation_created', (data) => {
      console.log('Socket event: annotation_created', data)
      // Reload annotations only if viewing the same dataset
      if (data.dataset_id && data.dataset_id === selectedDatasetIdRef.current) {
        console.log('Reloading annotations for current dataset')
        loadAnnotations(data.dataset_id)
      }
    })

    newSocket.on('annotation_updated', (data) => {
      console.log('Socket event: annotation_updated', data)
      if (data.dataset_id && data.dataset_id === selectedDatasetIdRef.current) {
        loadAnnotations(data.dataset_id)
      }
    })

    newSocket.on('annotation_deleted', (data) => {
      console.log('Socket event: annotation_deleted', data)
      if (data.dataset_id && data.dataset_id === selectedDatasetIdRef.current) {
        loadAnnotations(data.dataset_id)
      }
    })
    
    newSocket.on('user_joined', (data) => {
      console.log('User joined:', data.user)
      setConnectedUsers(prev => {
        if (!prev.includes(data.user)) {
          return [...prev, data.user]
        }
        return prev
      })
    })

    return () => {
      console.log('Closing socket connection')
      newSocket.close()
    }
  }, [currentUser]) // Removed selectedDataset dependency

  // Load datasets on mount
  useEffect(() => {
    loadDatasets()
  }, [])

  const loadDatasets = async () => {
    try {
      const response = await axios.get(`${API_URL}/api/datasets/`)
      setDatasets(response.data.datasets)
    } catch (error) {
      console.error('Error loading datasets:', error)
    }
  }

  const handleDatasetSelect = async (dataset) => {
    console.log('Dataset selected:', dataset)
    
    // Update the ref to track current dataset
    selectedDatasetIdRef.current = dataset.id
    
    // Fetch full dataset details including metadata
    try {
      const response = await axios.get(`${API_URL}/api/datasets/${dataset.id}`)
      console.log('Full dataset loaded:', response.data)
      setSelectedDataset(response.data)
      await loadAnnotations(dataset.id)
      
      // Join dataset room for real-time updates
      if (socket && currentUser) {
        socket.emit('join_dataset', {
          dataset_id: dataset.id,
          user: currentUser
        })
      }
    } catch (error) {
      console.error('Error loading dataset details:', error)
      alert('Error loading dataset: ' + error.message)
    }
  }

  const handleUploadSuccess = () => {
    loadDatasets()
  }

  const handleAnnotationCreate = async (annotation) => {
    if (!selectedDataset) return
    
    try {
      console.log('Creating annotation:', annotation)
      const response = await axios.post(`${API_URL}/api/annotations/`, {
        dataset_id: selectedDataset.id,
        onset: annotation.onset,
        duration: annotation.duration,
        description: annotation.description,
        user: currentUser || 'anonymous'
      })
      console.log('Annotation created successfully:', response.data)
      
      // Broadcast to other users via Socket.IO
      if (socket) {
        socket.emit('annotation_created', {
          dataset_id: selectedDataset.id,
          annotation: response.data
        })
      }
      
      // Reload annotations to update the UI
      await loadAnnotations(selectedDataset.id)
    } catch (error) {
      console.error('Error creating annotation:', error)
      alert('Failed to create annotation: ' + error.message)
    }
  }

  return (
    <div className="app">
      <header className="app-header">
        <h1>🧠 EEG/MEG Annotation Platform</h1>
        <div className="user-info">
          <span>👤 {currentUser || 'Loading...'}</span>
          {connectedUsers.length > 1 && (
            <span style={{fontSize: '12px', color: '#666', marginLeft: '10px'}}>
              👥 {connectedUsers.length} users online
            </span>
          )}
          {selectedDataset && (
            <span className="dataset-name">
              📊 {selectedDataset.filename}
            </span>
          )}
        </div>
      </header>

      <div className="app-body">
        <aside className="sidebar">
          <DatasetManager
            datasets={datasets}
            selectedDataset={selectedDataset}
            onDatasetSelect={handleDatasetSelect}
            onUploadSuccess={handleUploadSuccess}
            onLoadDatasets={loadDatasets}
            onAnnotationsRefresh={() => selectedDataset && loadAnnotations(selectedDataset.id)}
          />
        </aside>

        <main className="main-content">
          {selectedDataset ? (
            <>
              <div style={{padding: '10px', background: '#f0f0f0', marginBottom: '10px'}}>
                DEBUG: Dataset selected - {selectedDataset.id} - {selectedDataset.filename}
              </div>
              <SignalViewer
                dataset={selectedDataset}
                annotations={annotations}
                customAnnotationTypes={customAnnotationTypes}
                onAnnotationCreate={handleAnnotationCreate}
                onAnnotationsRefresh={() => loadAnnotations(selectedDataset.id)}
                socket={socket}
                currentUser={currentUser}
              />
              <AnnotationPanel
                datasetId={selectedDataset.id}
                selectedDataset={selectedDataset}
                annotations={annotations}
                customAnnotationTypes={customAnnotationTypes}
                onCustomTypesChange={setCustomAnnotationTypes}
                onAnnotationsChange={() => loadAnnotations(selectedDataset.id)}
                socket={socket}
              />
            </>
          ) : (
            <div className="empty-state">
              <h2>👈 Select or upload a dataset to begin</h2>
              <p>Upload your EEG/MEG files or load sample datasets</p>
            </div>
          )}
        </main>
      </div>
    </div>
  )
}

export default App
