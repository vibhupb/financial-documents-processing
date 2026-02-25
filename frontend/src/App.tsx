import { Routes, Route, Navigate, useLocation } from 'react-router-dom';
import { AuthProvider, useAuth } from './contexts/AuthContext';
import Layout from './components/Layout';
import Login from './pages/Login';
import Dashboard from './pages/Dashboard';
import Documents from './pages/Documents';
import DocumentDetail from './pages/DocumentDetail';
import Upload from './pages/Upload';
import Review from './pages/Review';
import ReviewDocument from './pages/ReviewDocument';
import PluginList from './pages/PluginList';
import PluginWizard from './pages/PluginWizard';

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
            <Layout><Dashboard /></Layout>
          </ProtectedRoute>
        }
      />
      <Route
        path="/documents"
        element={
          <ProtectedRoute>
            <Layout><Documents /></Layout>
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
        path="/upload"
        element={
          <ProtectedRoute>
            <Layout><Upload /></Layout>
          </ProtectedRoute>
        }
      />
      <Route
        path="/review"
        element={
          <ProtectedRoute>
            <Layout><Review /></Layout>
          </ProtectedRoute>
        }
      />
      <Route
        path="/review/:documentId"
        element={
          <ProtectedRoute>
            <Layout><ReviewDocument /></Layout>
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
