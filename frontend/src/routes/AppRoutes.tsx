import React from 'react';
import { Routes, Route } from 'react-router-dom';
import MainLayout from '../layouts/MainLayout';

// Import placeholder pages
import DashboardPage from '../pages/DashboardPage';
import AnalyzeErrorsPage from '../pages/AnalyzeErrorsPage';
import CollectPage from '../pages/CollectPage';
// import ContainerPage from '../pages/ContainerPage';
// import EsParsePage from '../pages/EsParsePage';
// import FileParsePage from '../pages/FileParsePage';
// import NormalizeTsPage from '../pages/NormalizeTsPage';
// import PromptsManagerPage from '../pages/PromptsManagerPage';
// import NotFoundPage from '../pages/NotFoundPage'; // Placeholder for 404

const AppRoutes: React.FC = () => {
  return (
    <Routes>
      <Route element={<MainLayout />}>
        <Route path="/" element={<DashboardPage />} />
        <Route path="/analyze-errors" element={<AnalyzeErrorsPage />} />
        <Route path="/collect" element={<CollectPage />} />
        <Route path="/container" element={<ContainerPage />} />
        <Route path="/es-parser" element={<EsParsePage />} />
        <Route path="/file-parser" element={<FileParsePage />} />
        <Route path="/normalize-ts" element={<NormalizeTsPage />} />
        <Route path="/prompts-manager" element={<PromptsManagerPage />} />
        <Route path="*" element={<NotFoundPage />} /> {/* Catch-all for 404 */}
      </Route>
    </Routes>
  );
};

export default AppRoutes;
