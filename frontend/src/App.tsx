import { Routes, Route } from 'react-router-dom';
import { DashboardLayout } from '@/layouts/DashboardLayout';
import { RequireAuth } from '@/components/auth/RequireAuth';
import Login from '@/pages/Login';
import Dashboard from '@/pages/Dashboard';
import Documents from '@/pages/Documents';
import Workspace from '@/pages/Workspace';
import Settings from '@/pages/Settings';
import { useTaskWebSocket } from '@/hooks/useTaskWebSocket';

function App() {
  useTaskWebSocket(); // Initialize global task listener

  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      
      <Route element={<RequireAuth><DashboardLayout /></RequireAuth>}>
        <Route path="/" element={<Dashboard />} />
        <Route path="/documents" element={<Documents />} />
        <Route path="/documents/:id" element={<Workspace />} />
        <Route path="/workspace/:id" element={<Workspace />} />
        <Route path="/settings" element={<Settings />} />
      </Route>
    </Routes>
  );
}

export default App;