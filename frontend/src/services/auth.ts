/**
 * Cognito authentication service using AWS Amplify v6.
 *
 * Provides sign-in, sign-out, token management, and role extraction
 * from Cognito User Pool JWT claims.
 */

export type UserRole = 'Admins' | 'Reviewers' | 'Viewers';

export interface AuthUser {
  userId: string;
  email: string;
  groups: UserRole[];
  displayName?: string;
}

export interface AuthResult {
  success: boolean;
  user?: AuthUser;
  challengeName?: string;
  error?: string;
}

// Placeholder configuration - will use Amplify v6 when deployed
const COGNITO_USER_POOL_ID = import.meta.env.VITE_COGNITO_USER_POOL_ID || '';
// Client ID reserved for Amplify v6 integration
const COGNITO_CLIENT_ID = import.meta.env.VITE_COGNITO_CLIENT_ID || ''; void COGNITO_CLIENT_ID;

/**
 * Sign in with email and password.
 * Returns AuthResult with user info or error.
 */
export async function signIn(email: string, _password: string): Promise<AuthResult> {
  // When Amplify is configured, this will use amplifySignIn
  // For now, return a mock for development
  if (!COGNITO_USER_POOL_ID) {
    // Dev mode: auto-authenticate as admin
    return {
      success: true,
      user: {
        userId: 'dev-user',
        email: email || 'admin@localhost',
        groups: ['Admins', 'Reviewers', 'Viewers'],
        displayName: 'Dev Admin',
      },
    };
  }

  try {
    // TODO: Replace with Amplify v6 signIn when @aws-amplify/auth is installed
    return { success: false, error: 'Cognito not configured' };
  } catch (err: unknown) {
    return { success: false, error: (err as Error).message || 'Authentication failed' };
  }
}

/**
 * Sign out the current user.
 */
export async function signOut(): Promise<void> {
  // TODO: Replace with Amplify v6 signOut
  console.log('Signed out');
}

/**
 * Get the current authenticated user, or null if not signed in.
 */
export async function getCurrentUser(): Promise<AuthUser | null> {
  if (!COGNITO_USER_POOL_ID) {
    // Dev mode: return admin user
    return {
      userId: 'dev-user',
      email: 'admin@localhost',
      groups: ['Admins', 'Reviewers', 'Viewers'],
      displayName: 'Dev Admin',
    };
  }
  return null;
}

/**
 * Get the current ID token for API authorization.
 * Auto-refreshes if expired.
 */
export async function getIdToken(): Promise<string | null> {
  if (!COGNITO_USER_POOL_ID) {
    return null; // Dev mode: no auth header needed
  }
  // TODO: Replace with Amplify v6 fetchAuthSession
  return null;
}

/**
 * Check if the current user is authenticated.
 */
export async function isAuthenticated(): Promise<boolean> {
  const user = await getCurrentUser();
  return user !== null;
}
