import { ReactNode } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { FileText, Puzzle, LogOut, Inbox } from 'lucide-react';
import clsx from 'clsx';
import { useAuth } from '../contexts/AuthContext';
import { api } from '../services/api';

interface LayoutProps {
  children: ReactNode;
}

export default function Layout({ children }: LayoutProps) {
  const location = useLocation();
  const { user, userGroups, signOut, hasRole } = useAuth();

  // Fetch metrics for the attention badge on Work Queue nav item
  const { data: metrics } = useQuery({
    queryKey: ['metrics'],
    queryFn: api.getMetrics,
    refetchInterval: 15000,
  });

  const attentionCount =
    (metrics?.statusCounts?.['FAILED'] || 0) +
    (metrics?.statusCounts?.['PENDING_REVIEW'] || 0);

  const navigation = [
    {
      name: 'Work Queue',
      href: '/',
      icon: Inbox,
      badge: attentionCount > 0 ? attentionCount : undefined,
    },
    ...(hasRole('Admins')
      ? [
          {
            name: 'Plugin Studio',
            href: '/config',
            icon: Puzzle,
            badge: undefined as number | undefined,
          },
        ]
      : []),
  ];

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Sidebar */}
      <div className="fixed inset-y-0 left-0 z-50 w-64 bg-white border-r border-gray-200 flex flex-col">
        {/* Logo */}
        <div className="flex items-center gap-3 h-16 px-6 border-b border-gray-200">
          <div className="w-8 h-8 bg-primary-600 rounded-lg flex items-center justify-center">
            <FileText className="w-5 h-5 text-white" />
          </div>
          <div>
            <h1 className="font-semibold text-gray-900">FinDocs</h1>
            <p className="text-xs text-gray-500">Document Processing</p>
          </div>
        </div>

        {/* Navigation */}
        <nav className="flex-1 px-4 py-4 space-y-1">
          {navigation.map((item) => {
            const isActive =
              item.href === '/'
                ? location.pathname === '/'
                : location.pathname.startsWith(item.href);
            return (
              <Link
                key={item.name}
                to={item.href}
                className={clsx(
                  'flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium transition-colors',
                  isActive
                    ? 'bg-primary-50 text-primary-700'
                    : 'text-gray-600 hover:bg-gray-50 hover:text-gray-900'
                )}
              >
                <item.icon className="w-5 h-5" />
                <span className="flex-1">{item.name}</span>
                {item.badge !== undefined && (
                  <span className="inline-flex items-center justify-center min-w-[20px] h-5 px-1.5 rounded-full text-xs font-semibold bg-red-100 text-red-700">
                    {item.badge}
                  </span>
                )}
              </Link>
            );
          })}
        </nav>

        {/* User info + Sign out */}
        <div className="p-4 border-t border-gray-200">
          <div className="px-3 py-2 space-y-2">
            <div className="flex items-center gap-2">
              <div className="w-8 h-8 bg-gray-200 rounded-full flex items-center justify-center text-xs font-medium text-gray-600">
                {user?.displayName?.charAt(0).toUpperCase() ?? user?.email?.charAt(0).toUpperCase() ?? '?'}
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium text-gray-900 truncate">
                  {user?.displayName ?? user?.email ?? 'User'}
                </p>
                <p className="text-xs text-gray-500">
                  {userGroups[0] ?? 'Authenticated'}
                </p>
              </div>
            </div>
            <button
              onClick={signOut}
              className="w-full flex items-center gap-2 px-2 py-1.5 text-sm text-gray-600 hover:text-red-600 hover:bg-red-50 rounded-md transition-colors"
            >
              <LogOut className="w-4 h-4" />
              Sign out
            </button>
          </div>
        </div>
      </div>

      {/* Main content */}
      <div className="pl-64">
        <main className="p-8">{children}</main>
      </div>
    </div>
  );
}
