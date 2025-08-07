import React, { useState } from 'react';
import axios from 'axios';
import './App.css';

const API_BASE_URL = process.env.REACT_APP_API_BASE_URL;

function App() {
  const [file, setFile] = useState(null);
  const [loading, setLoading] = useState(false);
  const [uploadedData, setUploadedData] = useState(null);
  const [mappedData, setMappedData] = useState(null);
  const [pdfReady, setPdfReady] = useState(false);
  const [error, setError] = useState('');

  const handleFileChange = (event) => {
    const selectedFile = event.target.files[0];
    if (selectedFile && (selectedFile.name.endsWith('.xlsx') || selectedFile.name.endsWith('.xls'))) {
      setFile(selectedFile);
      setError('');
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
      const response = await axios.post(`${API_BASE_URL}/upload`, formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      });

      if (response.data.success) {
        setUploadedData(response.data.excel_data);
        setMappedData(response.data.mapped_data);
        setError('');
      }
    } catch (err) {
      setError(err.response?.data?.error || 'Upload failed');
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
      const response = await axios.post(`${API_BASE_URL}/generate-pdf`);
      
      if (response.data.success) {
        setPdfReady(true);
        setError('');
      }
    } catch (err) {
      setError(err.response?.data?.error || 'PDF generation failed');
    } finally {
      setLoading(false);
    }
  };

  const handleDownloadPDF = async () => {
    try {
      const response = await axios.get(`${API_BASE_URL}/download-pdf`, {
        responseType: 'blob',
      });

      // Create blob link to download
      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', 'form_w7_filled.pdf');
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
    } catch (err) {
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

  return (
    <div className="App">
      <header className="App-header">
        <h1>IRS Form W-7 Processor</h1>
        <p>Upload Excel file to generate filled W-7 form</p>
      </header>

      <main className="main-content">
        {/* File Upload Section */}
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
            {loading ? 'Processing...' : 'Upload & Process'}
          </button>
        </div>

        {/* Error Display */}
        {error && (
          <div className="error-message">
            <p>❌ {error}</p>
          </div>
        )}

        {/* Data Display */}
        {uploadedData && (
          <div className="results-section">
            {renderDataTable(uploadedData, "📊 Extracted Excel Data")}
            
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
              </>
            )}
          </div>
        )}

        {/* Instructions */}
        <div className="instructions">
          <h3>📋 Instructions:</h3>
          <ol>
            <li>Prepare an Excel file with columns like: Full Name, Date of Birth, Country of Citizenship, Address, Passport Number, etc.</li>
            <li>Upload the Excel file using the button above</li>
            <li>Review the extracted and AI-mapped data</li>
            <li>Generate and download the filled W-7 PDF form</li>
          </ol>
        </div>
      </main>
    </div>
  );
}

export default App;