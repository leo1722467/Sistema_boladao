async function loadModels() {
  const r = await fetch('/admin/models', { credentials: 'include' });
  if (!r.ok) {
    document.getElementById('models').innerText = 'Failed to load models';
    return;
  }
  const models = await r.json();
  const list = document.createElement('ul');
  models.forEach(m => {
    const li = document.createElement('li');
    const a = document.createElement('a');
    a.href = `/admin/${m}`;
    a.innerText = m;
    li.appendChild(a);
    list.appendChild(li);
  });
  const container = document.getElementById('models');
  container.innerHTML = '';
  container.appendChild(list);
}

window.addEventListener('DOMContentLoaded', loadModels);