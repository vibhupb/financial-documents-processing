import {
  createContext,
  useContext,
  useEffect,
  useState,
  useCallback,
  type ReactNode,
} from 'react';
import {
  signIn as authSignIn,
  signOut as authSignOut,
  getCurrentUser,
  type AuthUser,
  type UserRole,
  type AuthResult,
} from '../services/auth';

interface AuthContextValue {
  user: AuthUser | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  userGroups: UserRole[];
  signIn: (email: string, password: string) => Promise<AuthResult>;
  signOut: () => Promise<void>;
  hasRole: (role: UserRole) => boolean;
  hasAnyRole: (...roles: UserRole[]) => boolean;
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [userGroups, setUserGroups] = useState<UserRole[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    checkAuthState();
  }, []);

  async function checkAuthState() {
    try {
      setIsLoading(true);
      const currentUser = await getCurrentUser();
      if (currentUser) {
        setUser(currentUser);
        setUserGroups(currentUser.groups);
      }
    } catch {
      setUser(null);
      setUserGroups([]);
    } finally {
      setIsLoading(false);
    }
  }

  const signIn = useCallback(async (email: string, password: string): Promise<AuthResult> => {
    const result = await authSignIn(email, password);
    if (result.success && result.user) {
      setUser(result.user);
      setUserGroups(result.user.groups);
    }
    return result;
  }, []);

  const signOut = useCallback(async () => {
    await authSignOut();
    setUser(null);
    setUserGroups([]);
  }, []);

  const hasRole = useCallback(
    (role: UserRole) => userGroups.includes(role),
    [userGroups]
  );

  const hasAnyRole = useCallback(
    (...roles: UserRole[]) => roles.some((role) => userGroups.includes(role)),
    [userGroups]
  );

  return (
    <AuthContext.Provider
      value={{
        user,
        isAuthenticated: user !== null,
        isLoading,
        userGroups,
        signIn,
        signOut,
        hasRole,
        hasAnyRole,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}
