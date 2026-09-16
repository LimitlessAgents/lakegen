import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';
import { LakeGenProvider } from './state/LakeGenContext';
import { Sidebar } from './components/Sidebar';
import { ToastProvider } from './components/ui/Toast';
import { Agent } from './pages/Agent';
import { Catalogs } from './pages/Catalogs';

export function App() {
  return (
    <ToastProvider>
      <LakeGenProvider>
        <BrowserRouter>
          <div className="flex h-full min-h-full w-full flex-col bg-canvas text-ink md:flex-row">
            <Sidebar />
            <div className="flex min-h-0 min-w-0 flex-1 flex-col">
              <Routes>
                <Route path="/" element={<Navigate to="/agent" replace />} />
                <Route path="/agent" element={<Agent />} />
                <Route path="/catalogs" element={<Catalogs />} />
                <Route path="*" element={<Navigate to="/agent" replace />} />
              </Routes>
            </div>
          </div>
        </BrowserRouter>
      </LakeGenProvider>
    </ToastProvider>
  );
}
