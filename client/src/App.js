import React, { useState } from 'react';
import axios from 'axios';
import './App.css';

const API_BASE_URL = process.env.REACT_APP_API_BASE_URL;

function App() {
  const [file, setFile] = useState(null);
  const [loading, setLoading] = useState(false);
  const [clientList, setClientList] = useState([]);
  const [selectedClient, setSelectedClient] = useState({ first_name: '', last_name: '' });
  const [uploadedData, setUploadedData] = useState(null);
  const [mappedData, setMappedData] = useState(null);
  const [pdfReady, setPdfReady] = useState(false);
  const [error, setError] = useState('');
  const [step, setStep] = useState(1); // 1: Upload, 2: Select Client, 3: Process

  const handleFileChange = (event) => {
    const selectedFile = event.target.files[0];
    if (selectedFile && (selectedFile.name.endsWith('.xlsx') || selectedFile.name.endsWith('.xls'))) {
      setFile(selectedFile);
      setError('');
      // Reset all other states when a new file is selected
      setClientList([]);
      setSelectedClient({ first_name: '', last_name: '' });
      setUploadedData(null);
      setMappedData(null);
      setPdfReady(false);
      setStep(1);
    } else {
      setError('Please select a valid Excel file (.xlsx or .xls)');
      setFile(null);
    }
  };

  const handleUpload = async () => {
    if (!file) {
      setError('Please select a file first');
      return;
    }

    setLoading(true);
    setError('');
    
    const formData = new FormData();
    formData.append('file', file);

    try {
      console.log('Making request to:', `${API_BASE_URL}/upload`);
      const response = await axios.post(`${API_BASE_URL}/upload`, formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      });

      if (response.data.success) {
        setClientList(response.data.client_list);
        setStep(2); // Move to client selection step
        setError('');
      }
    } catch (err) {
      console.error('Upload error:', err);
      setError(err.response?.data?.error || 'Upload failed');
      setClientList([]);
    } finally {
      setLoading(false);
    }
  };

  const handleClientNameChange = (field, value) => {
    setSelectedClient(prev => ({
      ...prev,
      [field]: value
    }));
  };

  const handleClientSelect = (client) => {
    setSelectedClient({
      first_name: client.first_name,
      last_name: client.last_name
    });
  };

  const handleProcessClient = async () => {
    if (!selectedClient.first_name || !selectedClient.last_name) {
      setError('Please enter both first name and last name');
      return;
    }

    setLoading(true);
    setError('');

    try {
      console.log('Making request to:', `${API_BASE_URL}/process-client`);
      const response = await axios.post(`${API_BASE_URL}/process-client`, {
        first_name: selectedClient.first_name,
        last_name: selectedClient.last_name
      });

      if (response.data.success) {
        setUploadedData(response.data.excel_data);
        setMappedData(response.data.mapped_data);
        setStep(3); // Move to processing step
        setError('');
      }
    } catch (err) {
      console.error('Process client error:', err);
      if (err.response?.status === 404) {
        setError(`Client "${selectedClient.first_name} ${selectedClient.last_name}" not found. Please check the spelling.`);
      } else {
        setError(err.response?.data?.error || 'Client processing failed');
      }
      setUploadedData(null);
      setMappedData(null);
    } finally {
      setLoading(false);
    }
  };

  const handleGeneratePDF = async () => {
    if (!mappedData) {
      setError('No data available to generate PDF');
      return;
    }

    setLoading(true);
    setError('');

    try {
      console.log('Making request to:', `${API_BASE_URL}/generate-pdf`);
      const response = await axios.post(`${API_BASE_URL}/generate-pdf`);
      
      if (response.data.success) {
        setPdfReady(true);
        setError('');
      }
    } catch (err) {
      console.error('Generate PDF error:', err);
      setError(err.response?.data?.error || 'PDF generation failed');
    } finally {
      setLoading(false);
    }
  };

  const handleDownloadPDF = async () => {
    try {
      console.log('Making request to:', `${API_BASE_URL}/download-pdf`);
      const response = await axios.get(`${API_BASE_URL}/download-pdf`, {
        responseType: 'blob',
      });

      // Create blob link to download
      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', `form_w7_${selectedClient.first_name}_${selectedClient.last_name}.pdf`);
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
    } catch (err) {
      console.error('Download error:', err);
      setError('Download failed');
    }
  };

  const renderDataTable = (data, title) => {
    if (!data) return null;

    return (
      <div className="data-section">
        <h3>{title}</h3>
        <div className="data-table">
          {Object.entries(data).map(([key, value]) => (
            <div key={key} className="data-row">
              <span className="data-key">{key.replace(/_/g, ' ').toUpperCase()}:</span>
              <span className="data-value">{value || 'N/A'}</span>
            </div>
          ))}
        </div>
      </div>
    );
  };

  const renderClientSelection = () => {
    if (step !== 2) return null;

    return (
      <div className="client-selection-section">
        <h3>👥 Select Client</h3>
        
        {/* Manual Name Input */}
        <div className="name-input-section">
          <h4>Enter Client Name:</h4>
          <div className="name-inputs">
            <input
              type="text"
              placeholder="First Name"
              value={selectedClient.first_name}
              onChange={(e) => handleClientNameChange('first_name', e.target.value)}
              className="name-input"
            />
            <input
              type="text"
              placeholder="Last Name"
              value={selectedClient.last_name}
              onChange={(e) => handleClientNameChange('last_name', e.target.value)}
              className="name-input"
            />
          </div>
          <button
            onClick={handleProcessClient}
            disabled={loading || !selectedClient.first_name || !selectedClient.last_name}
            className="btn btn-primary"
          >
            {loading ? 'Processing...' : 'Process Client'}
          </button>
        </div>

        {/* OR Divider */}
        <div className="divider">
          <span>OR</span>
        </div>

        {/* Client List */}
        <div className="client-list-section">
          <h4>Choose from available clients ({clientList.length} found):</h4>
          <div className="client-list">
            {clientList.map((client, index) => (
              <div
                key={index}
                className={`client-item ${
                  selectedClient.first_name === client.first_name && 
                  selectedClient.last_name === client.last_name ? 'selected' : ''
                }`}
                onClick={() => handleClientSelect(client)}
              >
                <span className="client-name">{client.full_name}</span>
                <button
                  className="btn btn-small"
                  onClick={(e) => {
                    e.stopPropagation();
                    handleClientSelect(client);
                    handleProcessClient();
                  }}
                  disabled={loading}
                >
                  Select & Process
                </button>
              </div>
            ))}
          </div>
        </div>
      </div>
    );
  };

  return (
    <div className="App">
      <header className="App-header">
        <h1>IRS Form W-7 Processor</h1>
        <p>Upload Excel file with multiple clients to generate filled W-7 forms</p>
      </header>

      <main className="main-content">
        {/* Progress Indicator */}
        <div className="progress-indicator">
          <div className={`step ${step >= 1 ? 'active' : ''} ${step > 1 ? 'completed' : ''}`}>
            1. Upload File
          </div>
          <div className={`step ${step >= 2 ? 'active' : ''} ${step > 2 ? 'completed' : ''}`}>
            2. Select Client
          </div>
          <div className={`step ${step >= 3 ? 'active' : ''}`}>
            3. Generate PDF
          </div>
        </div>

        {/* Step 1: File Upload */}
        {step === 1 && (
          <div className="upload-section">
            <div className="file-input-wrapper">
              <input
                type="file"
                id="file-input"
                accept=".xlsx,.xls"
                onChange={handleFileChange}
                className="file-input"
              />
              <label htmlFor="file-input" className="file-input-label">
                {file ? file.name : 'Choose Excel File'}
              </label>
            </div>
            
            <button
              onClick={handleUpload}
              disabled={!file || loading}
              className="btn btn-primary"
            >
              {loading ? 'Processing...' : 'Upload & Scan for Clients'}
            </button>
          </div>
        )}

        {/* Step 2: Client Selection */}
        {renderClientSelection()}

        {/* Error Display */}
        {error && (
          <div className="error-message">
            <p>❌ {error}</p>
          </div>
        )}

        {/* Step 3: Data Display and PDF Generation */}
        {step === 3 && uploadedData && (
          <div className="results-section">
            <div className="selected-client-info">
              <h3>📋 Selected Client: {selectedClient.first_name} {selectedClient.last_name}</h3>
            </div>
            
            {renderDataTable(uploadedData, "📊 Extracted Client Data")}
            
            {mappedData && (
              <>
                {renderDataTable(mappedData, "🤖 AI-Mapped W-7 Fields")}
                
                <div className="pdf-section">
                  <button
                    onClick={handleGeneratePDF}
                    disabled={loading}
                    className="btn btn-secondary"
                  >
                    {loading ? 'Generating...' : 'Generate W-7 PDF'}
                  </button>
                  
                  {pdfReady && (
                    <button
                      onClick={handleDownloadPDF}
                      className="btn btn-success"
                    >
                      📄 Download PDF
                    </button>
                  )}
                </div>

                {/* Back to Client Selection */}
                <div className="navigation-section">
                  <button
                    onClick={() => {
                      setStep(2);
                      setUploadedData(null);
                      setMappedData(null);
                      setPdfReady(false);
                      setSelectedClient({ first_name: '', last_name: '' });
                    }}
                    className="btn btn-outline"
                  >
                    ← Select Different Client
                  </button>
                </div>
              </>
            )}
          </div>
        )}

        {/* Instructions */}
        <div className="instructions">
          <h3>📋 Instructions:</h3>
          <ol>
            <li>Prepare an Excel file with multiple clients, including columns like: First Name, Last Name, Date of Birth, Country of Citizenship, Address, Passport Number, etc.</li>
            <li>Upload the Excel file to scan for available clients</li>
            <li>Select a client by entering their name or choosing from the list</li>
            <li>Review the extracted and AI-mapped data for the selected client</li>
            <li>Generate and download the filled W-7 PDF form for that client</li>
            <li>Repeat the process for additional clients as needed</li>
          </ol>
        </div>
      </main>
    </div>
  );
}

export default App;