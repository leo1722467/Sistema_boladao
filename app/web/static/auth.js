/**
 * Enhanced authentication management for client-side
 * Handles session validation, automatic redirects, and browser back button issues
 */

class AuthManager {
    constructor() {
        this.checkInterval = null;
        this.isCheckingAuth = false;
        this.init();
    }

    init() {
        // Check authentication on page load
        this.checkAuthentication();
        
        // Set up periodic authentication checks
        this.startPeriodicCheck();
        
        // Handle browser navigation events
        this.setupNavigationHandlers();
        
        // Handle visibility change (when user returns to tab)
        this.setupVisibilityHandler();
    }

    /**
     * Get access token from cookie
     */
    getAccessToken() {
        const tokenCookie = document.cookie
            .split('; ')
            .find(row => row.startsWith('access_token='));
        return tokenCookie ? tokenCookie.split('=')[1] : null;
    }

    /**
     * Check if current page requires authentication
     */
    requiresAuthentication() {
        const path = window.location.pathname;
        const protectedPaths = ['/admin', '/dashboard', '/kb'];
        return protectedPaths.some(protectedPath => path.startsWith(protectedPath));
    }

    /**
     * Validate authentication with server
     */
    async validateAuthentication() {
        if (this.isCheckingAuth) return true; // Prevent concurrent checks
        
        this.isCheckingAuth = true;
        
        try {
            const token = this.getAccessToken();
            if (!token) {
                this.isCheckingAuth = false;
                return false;
            }

            const response = await fetch('/auth/me', {
                method: 'GET',
                credentials: 'include',
                headers: {
                    'Authorization': `Bearer ${token}`
                }
            });

            this.isCheckingAuth = false;
            if (response.redirected && response.url && response.url.includes('/web/login')) {
                return false;
            }
            return response.ok;
        } catch (error) {
            console.error('Authentication check failed:', error);
            this.isCheckingAuth = false;
            return false;
        }
    }

    /**
     * Check authentication and redirect if necessary
     */
    async checkAuthentication() {
        if (!this.requiresAuthentication()) {
            return; // No auth required for this page
        }

        const isAuthenticated = await this.validateAuthentication();
        
        if (!isAuthenticated) {
            console.log('Authentication failed, redirecting to login');
            this.redirectToLogin();
        }
    }

    /**
     * Redirect to login page
     */
    redirectToLogin() {
        // Clear any existing token
        document.cookie = 'access_token=; Path=/; Expires=Thu, 01 Jan 1970 00:00:01 GMT;';
        
        // Redirect to login
        window.location.href = '/web/login';
    }

    /**
     * Start periodic authentication checks
     */
    startPeriodicCheck() {
        // Check every 5 minutes
        this.checkInterval = setInterval(() => {
            this.checkAuthentication();
        }, 5 * 60 * 1000);
    }

    /**
     * Stop periodic authentication checks
     */
    stopPeriodicCheck() {
        if (this.checkInterval) {
            clearInterval(this.checkInterval);
            this.checkInterval = null;
        }
    }

    /**
     * Setup navigation event handlers
     */
    setupNavigationHandlers() {
        // Handle browser back/forward buttons
        window.addEventListener('popstate', () => {
            // Small delay to ensure page has loaded
            setTimeout(() => {
                this.checkAuthentication();
            }, 100);
        });

        // Handle page show event (when returning from cache)
        window.addEventListener('pageshow', (event) => {
            if (event.persisted) {
                // Page was loaded from cache, check auth
                this.checkAuthentication();
            }
        });
    }

    /**
     * Setup visibility change handler
     */
    setupVisibilityHandler() {
        document.addEventListener('visibilitychange', () => {
            if (!document.hidden) {
                // User returned to tab, check authentication
                this.checkAuthentication();
            }
        });
    }

    /**
     * Logout user
     */
    async logout() {
        try {
            // Call logout endpoint
            await fetch('/web/logout', {
                method: 'GET',
                credentials: 'include'
            });
        } catch (error) {
            console.error('Logout request failed:', error);
        }
        
        // Clear token and redirect regardless of server response
        document.cookie = 'access_token=; Path=/; Expires=Thu, 01 Jan 1970 00:00:01 GMT;';
        window.location.href = '/';
    }

    /**
     * Cleanup when page unloads
     */
    cleanup() {
        this.stopPeriodicCheck();
    }
}

// Initialize authentication manager
const authManager = new AuthManager();

// Cleanup on page unload
window.addEventListener('beforeunload', () => {
    authManager.cleanup();
});

// Export for global access
window.authManager = authManager;

// Global fetch wrapper to redirect to login when unauthenticated
(function() {
    const _fetch = window.fetch;
    window.fetch = async function(input, init) {
        try {
            const res = await _fetch(input, init);
            if (res && (res.status === 401 || (res.redirected && res.url && res.url.includes('/web/login')))) {
                authManager.redirectToLogin();
            }
            return res;
        } catch (err) {
            // Network or aborted: if page requires auth, redirect
            try {
                if (authManager.requiresAuthentication()) authManager.redirectToLogin();
            } catch {}
            throw err;
        }
    };
})();
