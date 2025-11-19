/**
 * Dashboard page showing dataset list and upload functionality.
 */

import { useState, useEffect, useRef } from 'react';
import { useRouter } from 'next/router';
import { useAuth } from '@/contexts/AuthContext';
import { listDatasets, uploadDataset, logout as apiLogout } from '@/lib/api';
import styles from '@/styles/Dashboard.module.css';

interface Dataset {
  id: string;
  name: string;
  columns: { name: string; type: string }[];
  row_count: number;
  created_at: string;
}

export default function Dashboard() {
  const router = useRouter();
  const { user, isLoading, isAuthenticated, logout } = useAuth();
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [datasets, setDatasets] = useState<Dataset[]>([]);
  const [isLoadingData, setIsLoadingData] = useState(true);
  const [isUploading, setIsUploading] = useState(false);
  const [error, setError] = useState('');
  const [uploadError, setUploadError] = useState('');

  // Redirect to login if not authenticated
  useEffect(() => {
    if (!isLoading && !isAuthenticated) {
      router.push('/login');
    }
  }, [isLoading, isAuthenticated, router]);

  // Fetch datasets
  useEffect(() => {
    if (isAuthenticated) {
      fetchDatasets();
    }
  }, [isAuthenticated]);

  const fetchDatasets = async () => {
    try {
      const response = await listDatasets();
      setDatasets(response.data);
      setError('');
    } catch (err: any) {
      setError('Failed to load datasets');
    } finally {
      setIsLoadingData(false);
    }
  };

  const handleFileSelect = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    // Client-side file size check (10MB)
    const maxSize = 10 * 1024 * 1024;
    if (file.size > maxSize) {
      setUploadError(`File size (${(file.size / 1024 / 1024).toFixed(2)}MB) exceeds maximum allowed size of 10MB`);
      return;
    }

    // Check file type
    if (!file.name.endsWith('.csv')) {
      setUploadError('Please select a CSV file');
      return;
    }

    setIsUploading(true);
    setUploadError('');

    try {
      await uploadDataset(file);
      await fetchDatasets(); // Refresh list
      if (fileInputRef.current) {
        fileInputRef.current.value = ''; // Reset file input
      }
    } catch (err: any) {
      setUploadError(err.response?.data?.detail || 'Upload failed. Please try again.');
    } finally {
      setIsUploading(false);
    }
  };

  const handleLogout = async () => {
    try {
      await apiLogout();
    } catch (err) {
      // Ignore logout errors
    }
    logout();
    router.push('/login');
  };

  const handleDatasetClick = (id: string) => {
    router.push(`/datasets/${id}`);
  };

  // Show loading while checking auth
  if (isLoading) {
    return <div className={styles.loading}>Loading...</div>;
  }

  // Don't render if not authenticated (will redirect)
  if (!isAuthenticated) {
    return null;
  }

  return (
    <div className={styles.container}>
      <header className={styles.header}>
        <h1>Analytics Dashboard</h1>
        <div className={styles.userInfo}>
          <span>{user?.email}</span>
          <button onClick={handleLogout} className={styles.logoutButton}>
            Logout
          </button>
        </div>
      </header>

      <main className={styles.main}>
        {/* Upload Section */}
        <section className={styles.uploadSection}>
          <h2>Upload Dataset</h2>
          <div className={styles.uploadArea}>
            <input
              ref={fileInputRef}
              type="file"
              accept=".csv"
              onChange={handleFileSelect}
              disabled={isUploading}
              id="file-upload"
              className={styles.fileInput}
            />
            <label htmlFor="file-upload" className={styles.fileLabel}>
              {isUploading ? 'Uploading...' : 'Choose CSV file (max 10MB)'}
            </label>
          </div>
          {uploadError && <div className={styles.uploadError}>{uploadError}</div>}
        </section>

        {/* Datasets List */}
        <section className={styles.datasetsSection}>
          <h2>Your Datasets</h2>

          {error && <div className={styles.error}>{error}</div>}

          {isLoadingData ? (
            <p>Loading datasets...</p>
          ) : datasets.length === 0 ? (
            <p className={styles.emptyState}>
              No datasets yet. Upload a CSV file to get started.
            </p>
          ) : (
            <div className={styles.datasetGrid}>
              {datasets.map((dataset) => (
                <div
                  key={dataset.id}
                  className={styles.datasetCard}
                  onClick={() => handleDatasetClick(dataset.id)}
                >
                  <h3>{dataset.name}</h3>
                  <div className={styles.datasetMeta}>
                    <span>{dataset.row_count.toLocaleString()} rows</span>
                    <span>{dataset.columns.length} columns</span>
                  </div>
                  <div className={styles.datasetDate}>
                    {new Date(dataset.created_at).toLocaleDateString()}
                  </div>
                </div>
              ))}
            </div>
          )}
        </section>
      </main>
    </div>
  );
}
