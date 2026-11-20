import React from 'react';
import { createRoot } from 'react-dom/client';
import '@fontsource/geist/latin-400.css';
import '@fontsource/geist/latin-700.css';
import VideoPage from './VideoPage.jsx';
import './video.css';

createRoot(document.getElementById('root')).render(<VideoPage />);
