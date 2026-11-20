import React from 'react';
import { createRoot } from 'react-dom/client';
import '@fontsource/geist/latin-400.css';
import '@fontsource/geist/latin-600.css';
import '@fontsource/geist/latin-700.css';
import '@fontsource/geist/latin-800.css';
import '@fontsource/geist-mono/latin-400.css';
import '@fontsource/geist-mono/latin-500.css';
import 'cesium/Build/Cesium/Widgets/widgets.css';
import App from './App.jsx';
import './styles.css';
import './brand-tokens.css';
import './theme.css';

createRoot(document.getElementById('root')).render(<App />);
