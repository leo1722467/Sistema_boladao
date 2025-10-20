async function loadItems() {
  const model = window.__MODEL__;
  const schResp = await fetch(`/admin/${model}/schema`, { credentials: 'include' });
  const r = await fetch(`/admin/${model}/items`, { credentials: 'include' });
  const table = document.getElementById('items-table');
  if (!r.ok || !schResp.ok) {
    table.innerHTML = '<tr><td>Failed to load items</td></tr>';
    return;
  }
  const schema = await schResp.json();
  const items = await r.json();
  if (items.length === 0) {
    table.innerHTML = '<tr><td>No items yet</td></tr>';
    return;
  }
  const cols = schema.columns.map(c => c.name);
  const thead = `<tr>${cols.map(c => `<th>${c}</th>`).join('')}<th>Actions</th></tr>`;
  const rows = items.map(it => {
    const id = it[schema.primary_key];
    const cells = cols.map(c => `<td>${it[c]}</td>`).join('');
    const actions = `<td>
      <button onclick="window.location.href='/admin/${model}/${id}'">Edit</button>
      <button onclick="deleteItem('${model}', ${id})">Delete</button>
    </td>`;
    return `<tr>${cells}${actions}</tr>`;
  }).join('');
  table.innerHTML = thead + rows;
}

async function deleteItem(model, id) {
  if (!confirm('Delete item #' + id + '?')) return;
  
  // Get access token from cookie
  const tokenCookie = document.cookie
    .split('; ')
    .find(row => row.startsWith('access_token='));
  const token = tokenCookie ? tokenCookie.split('=')[1] : null;
  
  const headers = {};
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }
  
  const r = await fetch(`/admin/${model}/items/${id}`, {
    method: 'DELETE',
    headers: headers,
    credentials: 'include'
  });
  if (r.ok) {
    loadItems();
  } else {
    alert('Failed to delete');
  }
}

window.addEventListener('DOMContentLoaded', loadItems);