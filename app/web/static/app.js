(() => {
  async function fetchMe() {
    try {
      const res = await fetch('/auth/me', { credentials: 'include' });
      if (res.ok) {
        const data = await res.json();
        const meEl = document.getElementById('me');
        if (meEl) meEl.textContent = `Olá, ${data.nome} (${data.email})`;
      } else if (res.status === 401) {
        // Authentication failed, let auth manager handle it
        if (window.authManager) {
          window.authManager.checkAuthentication();
        }
      }
    } catch (e) { 
      console.error('Failed to fetch user info:', e);
    }
  }

  function logout() {
    if (window.authManager) {
      window.authManager.logout();
    } else {
      // Fallback if auth manager not available
      window.location.href = '/web/logout';
    }
  }

  // Setup logout button
  const logoutBtn = document.getElementById('logout');
  if (logoutBtn) logoutBtn.addEventListener('click', logout);
  
  // Fetch user info
  fetchMe();
})();