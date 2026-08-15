import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';
import { LakeGenProvider } from './state/LakeGenContext';
import { Sidebar } from './components/Sidebar';
import { Agent } from './pages/Agent';
import { Catalogs } from './pages/Catalogs';

export function App() {
  return (
    <LakeGenProvider>
      <BrowserRouter>
        <div className="flex h-full min-h-full w-full bg-canvas text-ink">
          <Sidebar />
          <Routes>
            <Route path="/" element={<Navigate to="/agent" replace />} />
            <Route path="/agent" element={<Agent />} />
            <Route path="/catalogs" element={<Catalogs />} />
            <Route path="*" element={<Navigate to="/agent" replace />} />
          </Routes>
        </div>
      </BrowserRouter>
    </LakeGenProvider>
  );
}
