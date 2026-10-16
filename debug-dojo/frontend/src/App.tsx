import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { DojoScene } from './scene/DojoScene';
import { Header } from './components/Header';
import { PracticePage } from './pages/PracticePage';
import { LearnerPage } from './pages/LearnerPage';
import './styles/tokens.css';

export function App() {
  return (
    <BrowserRouter>
      {/* 3D Dojo Canvas Background Layer */}
      <DojoScene />

      {/* Accessible HTML UI Layer */}
      <div
        style={{
          position: 'relative',
          zIndex: 1,
          minHeight: '100vh',
          display: 'flex',
          flexDirection: 'column',
        }}
      >
        <Header />
        <main style={{ flex: 1 }}>
          <Routes>
            <Route path="/" element={<PracticePage />} />
            <Route path="/learner" element={<LearnerPage />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  );
}

export default App;
