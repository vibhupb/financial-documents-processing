import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import BaselineEditor from '../pages/BaselineEditor';
import { api } from '../services/api';
import { vi, describe, test, expect, beforeEach } from 'vitest';

vi.mock('../services/api', () => ({
  api: {
    getBaseline: vi.fn(),
    addRequirement: vi.fn(),
    updateRequirement: vi.fn(),
    deleteRequirement: vi.fn(),
    publishBaseline: vi.fn(),
  },
}));

const MOCK_BASELINE = {
  baselineId: 'bl-1',
  name: 'OCC Mortgage',
  status: 'draft',
  version: 0,
  description: 'Mortgage compliance',
  pluginIds: ['loan_package'],
  categories: ['Rates', 'Execution'],
  requirements: [
    {
      requirementId: 'req-001',
      text: 'Must specify APR',
      category: 'Rates',
      criticality: 'must-have',
      status: 'active',
    },
    {
      requirementId: 'req-002',
      text: 'Must include signature',
      category: 'Execution',
      criticality: 'should-have',
      status: 'active',
    },
  ],
};

function renderEditor() {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={['/baselines/bl-1']}>
        <Routes>
          <Route path="/baselines/:baselineId" element={<BaselineEditor />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>
  );
}

describe('BaselineEditor', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  test('renders requirements list and allows inline editing', async () => {
    (api.getBaseline as any).mockResolvedValue({ baseline: MOCK_BASELINE });
    renderEditor();
    await waitFor(() => {
      expect(screen.getByText('OCC Mortgage')).toBeInTheDocument();
      expect(screen.getByText('Must specify APR')).toBeInTheDocument();
      expect(screen.getByText('Must include signature')).toBeInTheDocument();
      expect(screen.getByText('must-have')).toBeInTheDocument();
    });
  });

  test('shows publish button for draft baselines', async () => {
    (api.getBaseline as any).mockResolvedValue({ baseline: MOCK_BASELINE });
    renderEditor();
    await waitFor(() => expect(screen.getByText(/publish/i)).toBeInTheDocument());
  });
});
