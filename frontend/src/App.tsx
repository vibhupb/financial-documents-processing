import { Routes, Route } from 'react-router-dom';
import Layout from './components/Layout';
import Dashboard from './pages/Dashboard';
import Documents from './pages/Documents';
import DocumentDetail from './pages/DocumentDetail';
import Upload from './pages/Upload';
import Review from './pages/Review';
import ReviewDocument from './pages/ReviewDocument';

export default function App() {
  return (
    <Layout>
      <Routes>
        <Route path="/" element={<Dashboard />} />
        <Route path="/documents" element={<Documents />} />
        <Route path="/documents/:documentId" element={<DocumentDetail />} />
        <Route path="/upload" element={<Upload />} />
        <Route path="/review" element={<Review />} />
        <Route path="/review/:documentId" element={<ReviewDocument />} />
      </Routes>
    </Layout>
  );
}
