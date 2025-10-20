let currentSchema = null;
let modalStack = [];
let modalCounter = 0;

async function inferColumns(model, isMainForm = false) {
  // Get access token from cookie
  const tokenCookie = document.cookie
    .split('; ')
    .find(row => row.startsWith('access_token='));
  const token = tokenCookie ? tokenCookie.split('=')[1] : null;
  
  const headers = {};
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }
  
  const r = await fetch(`/admin/${model}/schema`, { 
    credentials: 'include',
    headers: headers
  });
  if (!r.ok) return { columns: [], foreign_keys: {} };
  const s = await r.json();
  
  // Only set global currentSchema for main form, not for modals
  if (isMainForm) {
    currentSchema = s;
  }
  
  const pk = s.primary_key;
  return {
    columns: s.columns.filter(c => c.name !== pk && !c.server_default),
    foreign_keys: s.foreign_keys || {}
  };
}

async function loadForeignKeyOptions(model, field) {
  try {
    console.log(`Loading foreign key options for ${model}.${field}`);
    
    // Get access token from cookie
    const tokenCookie = document.cookie
      .split('; ')
      .find(row => row.startsWith('access_token='));
    const token = tokenCookie ? tokenCookie.split('=')[1] : null;
    
    const headers = {};
    if (token) {
      headers['Authorization'] = `Bearer ${token}`;
    }
    
    const r = await fetch(`/admin/${model}/foreign-key-options/${field}`, { 
      credentials: 'include',
      headers: headers
    });
    if (!r.ok) {
      console.warn(`Failed to load options for ${model}.${field}: ${r.status} ${r.statusText}`);
      return [];
    }
    const options = await r.json();
    console.log(`Loaded ${options.length} options for ${model}.${field}`);
    return options;
  } catch (error) {
    console.error(`Error loading options for ${model}.${field}:`, error);
    return [];
  }
}

function createFormField(column, foreignKeys, model) {
  const fieldContainer = document.createElement('div');
  fieldContainer.className = 'form-field';
  
  const label = document.createElement('label');
  label.innerText = formatFieldLabel(column.name);
  label.className = 'field-label';
  
  fieldContainer.appendChild(label);
  
  if (column.is_foreign_key && foreignKeys[column.name]) {
    // Create foreign key dropdown with + button
    const fkContainer = document.createElement('div');
    fkContainer.className = 'foreign-key-container';
    
    const select = document.createElement('select');
    select.name = column.name;
    select.className = 'form-select';
    
    // Add empty option
    const emptyOption = document.createElement('option');
    emptyOption.value = '';
    emptyOption.textContent = '-- Selecione --';
    select.appendChild(emptyOption);
    
    // Load options asynchronously
    loadForeignKeyOptions(model, column.name).then(options => {
      options.forEach(option => {
        const optionElement = document.createElement('option');
        optionElement.value = option.id;
        optionElement.textContent = option.display;
        select.appendChild(optionElement);
      });
    });
    
    fkContainer.appendChild(select);
    
    // Add + button for creating new related records
    const addButton = document.createElement('button');
    addButton.type = 'button';
    addButton.className = 'add-related-btn';
    addButton.innerHTML = '+';
    addButton.title = `Adicionar novo ${foreignKeys[column.name].target_model}`;
    addButton.onclick = () => openCreateRelatedModal(foreignKeys[column.name].target_model, select);
    
    fkContainer.appendChild(addButton);
    fieldContainer.appendChild(fkContainer);
    
  } else {
    // Create regular input field
    const input = document.createElement('input');
    input.name = column.name;
    input.className = 'form-input';
    
    // Set input type based on column type
    switch (column.type) {
      case 'Integer':
      case 'BigInteger':
        input.type = 'number';
        break;
      case 'Boolean':
        input.type = 'checkbox';
        input.className = 'form-checkbox';
        break;
      case 'DateTime':
        input.type = 'datetime-local';
        break;
      case 'Date':
        input.type = 'date';
        break;
      default:
        input.type = 'text';
    }
    
    if (!column.nullable) {
      input.required = true;
    }
    
    fieldContainer.appendChild(input);
  }
  
  return fieldContainer;
}

function formatFieldLabel(fieldName) {
  // Convert snake_case to readable format
  return fieldName
    .replace(/_id$/, '') // Remove _id suffix
    .replace(/_/g, ' ')  // Replace underscores with spaces
    .replace(/\b\w/g, l => l.toUpperCase()); // Capitalize first letter of each word
}

async function buildForm() {
  const model = window.__MODEL__;
  const { columns, foreign_keys } = await inferColumns(model, true);
  const form = document.getElementById('create-form');
  form.innerHTML = '';
  
  columns.forEach(column => {
    const fieldElement = createFormField(column, foreign_keys, model);
    form.appendChild(fieldElement);
  });
}

async function openCreateRelatedModal(targetModel, selectElement) {
  modalCounter++;
  const modalId = `modal-${modalCounter}`;
  const baseZIndex = 1000;
  const currentZIndex = baseZIndex + (modalStack.length * 10);
  
  // Create modal overlay
  const overlay = document.createElement('div');
  overlay.className = 'modal-overlay';
  overlay.id = modalId;
  overlay.style.zIndex = currentZIndex;
  
  const modal = document.createElement('div');
  modal.className = 'modal-content';
  
  const header = document.createElement('div');
  header.className = 'modal-header';
  header.innerHTML = `
    <h3>Criar novo ${targetModel}</h3>
    <button type="button" class="modal-close" onclick="closeModal('${modalId}')">×</button>
  `;
  
  const body = document.createElement('div');
  body.className = 'modal-body';
  body.innerHTML = `<div id="modal-form-${modalCounter}"></div>`;
  
  const footer = document.createElement('div');
  footer.className = 'modal-footer';
  footer.innerHTML = `
    <button type="button" class="btn btn-secondary" onclick="closeModal('${modalId}')">Cancelar</button>
    <button type="button" class="btn btn-primary" onclick="saveRelatedRecord('${targetModel}', this, '${modalId}', ${modalCounter})">Salvar</button>
  `;
  
  modal.appendChild(header);
  modal.appendChild(body);
  modal.appendChild(footer);
  overlay.appendChild(modal);
  
  // Add click outside to close
  overlay.addEventListener('click', (e) => {
    if (e.target === overlay) {
      closeModal(modalId);
    }
  });
  
  document.body.appendChild(overlay);
  
  // Add to modal stack
  modalStack.push({
    id: modalId,
    model: targetModel,
    selectElement: selectElement,
    formId: `modal-form-${modalCounter}`
  });
  
  // Build the form for the related model
  await buildRelatedForm(targetModel, modalCounter);
}

function closeModal(modalId) {
  const modal = document.getElementById(modalId);
  if (modal) {
    modal.remove();
    // Remove from stack
    modalStack = modalStack.filter(m => m.id !== modalId);
  }
}

async function buildRelatedForm(model, modalCounter) {
  const { columns, foreign_keys } = await inferColumns(model);
  const form = document.getElementById(`modal-form-${modalCounter}`);
  if (!form) return;
  
  form.innerHTML = '';
  
  columns.forEach(column => {
    const fieldElement = createFormField(column, foreign_keys, model);
    form.appendChild(fieldElement);
  });
}

async function updateParentModalDropdowns(savedModel, newRecord, currentModalId) {
  // Get all parent modals (excluding the current one that just saved)
  const parentModals = modalStack.filter(modal => modal.id !== currentModalId);
  
  for (const parentModal of parentModals) {
    // Find all select elements in this parent modal that reference the saved model
    const parentForm = document.getElementById(parentModal.formId);
    if (!parentForm) continue;
    
    const selectElements = parentForm.querySelectorAll('select');
    
    for (const select of selectElements) {
      const fieldName = select.name;
      if (!fieldName) continue;
      
      try {
        // Check if this select field references the model we just saved
        // We do this by trying to load foreign key options and seeing if it succeeds
        const options = await loadForeignKeyOptions(parentModal.model, fieldName);
        
        // Check if any of the options match our saved model by looking at the API endpoint pattern
        // If the field references our saved model, the options will include our new record
        const hasNewRecord = options.some(option => option.id === newRecord.id);
        
        if (hasNewRecord) {
          // Update this select with the new options including our new record
          const currentValue = select.value;
          select.innerHTML = '<option value="">-- Selecione --</option>';
          
          options.forEach(option => {
            const optionElement = document.createElement('option');
            optionElement.value = option.id;
            optionElement.textContent = option.display;
            
            // Preserve the previously selected value, or select the new record if no previous selection
            if (option.id.toString() === currentValue || (!currentValue && option.id === newRecord.id)) {
              optionElement.selected = true;
            }
            
            select.appendChild(optionElement);
          });
        }
      } catch (error) {
        // If loading foreign key options fails, this field doesn't reference our model
        // This is expected for fields that don't have foreign key relationships
        continue;
      }
    }
  }
}

async function saveRelatedRecord(model, button, modalId, modalCounter) {
  const form = document.getElementById(`modal-form-${modalCounter}`);
  if (!form) return;
  
  const payload = {};
  
  Array.from(form.querySelectorAll('input, select, textarea')).forEach(el => {
    if (el.name) {
      if (el.type === 'checkbox') {
        payload[el.name] = el.checked;
      } else {
        // Include all values, even empty ones, so backend can properly validate
        payload[el.name] = el.value;
      }
    }
  });
  
  try {
    button.disabled = true;
    button.textContent = 'Salvando...';
    
    // Get access token from cookie
    const tokenCookie = document.cookie
      .split('; ')
      .find(row => row.startsWith('access_token='));
    const token = tokenCookie ? tokenCookie.split('=')[1] : null;
    
    const headers = { 'Content-Type': 'application/json' };
    if (token) {
      headers['Authorization'] = `Bearer ${token}`;
    }
    
    const r = await fetch(`/admin/${model}/items`, {
      method: 'POST',
      headers: headers,
      body: JSON.stringify(payload),
      credentials: 'include'
    });
    
    if (r.ok) {
      const newRecord = await r.json();
      
      // Find the modal info in the stack
      const modalInfo = modalStack.find(m => m.id === modalId);
      if (modalInfo && modalInfo.selectElement) {
        // Update the specific select element that triggered this modal
        const select = modalInfo.selectElement;
        const fieldName = select.name;
        
        // Reload options for this specific select
        const options = await loadForeignKeyOptions(window.__MODEL__, fieldName);
        select.innerHTML = '<option value="">-- Selecione --</option>';
        options.forEach(option => {
          const optionElement = document.createElement('option');
          optionElement.value = option.id;
          optionElement.textContent = option.display;
          if (option.id === newRecord.id) {
            optionElement.selected = true;
          }
          select.appendChild(optionElement);
        });
      }
      
      // Cascade update: refresh all parent modal dropdowns that reference the same model
      await updateParentModalDropdowns(model, newRecord, modalId);
      
      // Close this specific modal
      closeModal(modalId);
      
    } else {
      const errorText = await r.text();
      try {
        const errorData = JSON.parse(errorText);
        const errorMessage = errorData.detail || 'Erro desconhecido';
        alert(`Erro ao salvar: ${errorMessage}`);
      } catch (parseError) {
        // Fallback to raw text if JSON parsing fails
        alert(`Erro ao salvar: ${errorText}`);
      }
    }
  } catch (error) {
    alert(`Erro ao salvar: ${error.message}`);
  } finally {
    button.disabled = false;
    button.textContent = 'Salvar';
  }
}

async function save() {
  const model = window.__MODEL__;
  const form = document.getElementById('create-form');
  const payload = {};
  
  Array.from(form.elements).forEach(el => {
    if (el.name) {
      if (el.type === 'checkbox') {
        payload[el.name] = el.checked;
      } else if (el.value) {
        // Convert to appropriate type for foreign keys
        if (el.name.endsWith('_id') && el.value) {
          payload[el.name] = parseInt(el.value);
        } else if (el.type === 'datetime-local' && el.value) {
          // Format datetime-local value to ISO string with seconds
          payload[el.name] = el.value + ':00';
        } else {
          payload[el.name] = el.value;
        }
      }
    }
  });
  
  try {
    const saveBtn = document.getElementById('save-btn');
    saveBtn.disabled = true;
    saveBtn.textContent = 'Salvando...';
    
    // Get access token from cookie
    const tokenCookie = document.cookie
      .split('; ')
      .find(row => row.startsWith('access_token='));
    const token = tokenCookie ? tokenCookie.split('=')[1] : null;
    
    const headers = { 'Content-Type': 'application/json' };
    if (token) {
      headers['Authorization'] = `Bearer ${token}`;
    }
    
    const r = await fetch(`/admin/${model}/items`, {
      method: 'POST',
      headers: headers,
      body: JSON.stringify(payload),
      credentials: 'include'
    });
    
    if (r.ok) {
      window.location.href = `/admin/${model}`;
    } else {
      const t = await r.text();
      try {
        const errorData = JSON.parse(t);
        const errorMessage = errorData.detail || 'Erro desconhecido';
        document.getElementById('error').innerText = errorMessage;
      } catch (parseError) {
        // Fallback to raw text if JSON parsing fails
        document.getElementById('error').innerText = t;
      }
    }
  } catch (error) {
    document.getElementById('error').innerText = `Erro: ${error.message}`;
  } finally {
    const saveBtn = document.getElementById('save-btn');
    saveBtn.disabled = false;
    saveBtn.textContent = 'Salvar Registro';
  }
}

window.addEventListener('DOMContentLoaded', async () => {
  await buildForm();
  document.getElementById('save-btn').addEventListener('click', save);
});