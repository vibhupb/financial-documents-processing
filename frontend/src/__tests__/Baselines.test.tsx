import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import Baselines from '../pages/Baselines';
import { api } from '../services/api';
import { vi, describe, test, expect, beforeEach } from 'vitest';

vi.mock('../services/api', () => ({
  api: {
    listBaselines: vi.fn(),
    createBaseline: vi.fn(),
  },
}));

function renderWithProviders(ui: React.ReactElement) {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter>{ui}</MemoryRouter>
    </QueryClientProvider>
  );
}

describe('Baselines', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  test('renders baselines list with status badges', async () => {
    (api.listBaselines as any).mockResolvedValue({
      baselines: [
        {
          baselineId: 'bl-1',
          name: 'OCC Mortgage',
          status: 'published',
          pluginIds: ['loan_package'],
          requirements: [{}, {}, {}],
        },
        {
          baselineId: 'bl-2',
          name: 'Draft Test',
          status: 'draft',
          pluginIds: [],
          requirements: [],
        },
      ],
    });
    renderWithProviders(<Baselines />);
    await waitFor(() => {
      expect(screen.getByText('OCC Mortgage')).toBeInTheDocument();
      expect(screen.getByText('3 requirements')).toBeInTheDocument();
      expect(screen.getByText('Draft Test')).toBeInTheDocument();
      // "published" appears both in filter tabs and status badge
      expect(screen.getAllByText('published')).toHaveLength(2);
    });
  });

  test('shows create baseline button', async () => {
    (api.listBaselines as any).mockResolvedValue({ baselines: [] });
    renderWithProviders(<Baselines />);
    await waitFor(() => {
      expect(screen.getByText(/create baseline/i)).toBeInTheDocument();
    });
  });
});
