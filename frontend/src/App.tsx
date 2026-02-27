import { Routes, Route, Navigate, useLocation } from 'react-router-dom';
import { AuthProvider, useAuth } from './contexts/AuthContext';
import Layout from './components/Layout';
import Login from './pages/Login';
import WorkQueue from './pages/WorkQueue';
import DocumentDetail from './pages/DocumentDetail';
import PluginList from './pages/PluginList';
import PluginWizard from './pages/PluginWizard';
import PluginEditor from './pages/PluginEditor';

function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { isAuthenticated, isLoading } = useAuth();
  const location = useLocation();

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50">
        <div className="text-center">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-600 mx-auto" />
          <p className="mt-4 text-sm text-gray-500">Loading...</p>
        </div>
      </div>
    );
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" state={{ from: location.pathname }} replace />;
  }

  return <>{children}</>;
}

function AppRoutes() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route
        path="/"
        element={
          <ProtectedRoute>
            <Layout><WorkQueue /></Layout>
          </ProtectedRoute>
        }
      />
      <Route
        path="/documents/:documentId"
        element={
          <ProtectedRoute>
            <Layout><DocumentDetail /></Layout>
          </ProtectedRoute>
        }
      />
      <Route
        path="/config"
        element={
          <ProtectedRoute>
            <Layout><PluginList /></Layout>
          </ProtectedRoute>
        }
      />
      <Route
        path="/config/new"
        element={
          <ProtectedRoute>
            <Layout><PluginWizard /></Layout>
          </ProtectedRoute>
        }
      />
      <Route
        path="/config/:pluginId"
        element={
          <ProtectedRoute>
            <Layout><PluginEditor /></Layout>
          </ProtectedRoute>
        }
      />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}

export default function App() {
  return (
    <AuthProvider>
      <AppRoutes />
    </AuthProvider>
  );
}
