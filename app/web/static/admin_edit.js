const tokenCookie = document.cookie.split('; ').find(row => row.startsWith('access_token='));
const accessToken = tokenCookie ? tokenCookie.split('=')[1] : null;

let modalStack = [];
let modalCounter = 0;

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

async function createRelatedRecord(relatedModel, formData) {
  try {
    const response = await fetch(`/admin/${relatedModel}/items`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(formData),
      credentials: 'include'
    });
    
    if (response.ok) {
      return await response.json();
    } else {
      const errorText = await response.text();
      throw new Error(errorText);
    }
  } catch (error) {
    console.error('Error creating related record:', error);
    throw error;
  }
}

function closeModal(modalId) {
  const modal = document.getElementById(modalId);
  if (modal) {
    modal.remove();
    // Remove from stack
    modalStack = modalStack.filter(m => m.id !== modalId);
  }
}

async function showCreateRelatedModal(relatedModel, fieldName, selectElement) {
  modalCounter++;
  const modalId = `modal-${modalCounter}`;
  const baseZIndex = 1000;
  const zIndex = baseZIndex + (modalStack.length * 10);
  
  // Create modal overlay
  const overlay = document.createElement('div');
  overlay.className = 'modal-overlay';
  overlay.id = modalId;
  overlay.style.zIndex = zIndex;
  
  // Create modal content
  const modal = document.createElement('div');
  modal.className = 'modal-content';
  
  // Create header
  const header = document.createElement('div');
  header.className = 'modal-header';
  header.innerHTML = `
    <h3>Criar novo ${relatedModel}</h3>
    <button type="button" class="modal-close" onclick="closeModal('${modalId}')">&times;</button>
  `;
  
  // Create body
  const body = document.createElement('div');
  body.className = 'modal-body';
  body.innerHTML = `<form id="modal-form-${modalCounter}"></form>`;
  
  // Create footer
  const footer = document.createElement('div');
  footer.className = 'modal-footer';
  footer.innerHTML = `
    <button type="button" class="btn btn-secondary" onclick="closeModal('${modalId}')">Cancelar</button>
    <button type="button" class="btn btn-primary" onclick="saveRelatedRecord('${relatedModel}', this, '${modalId}', ${modalCounter})">Salvar</button>
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
    model: relatedModel,
    selectElement: selectElement,
    formId: `modal-form-${modalCounter}`
  });
  
  // Build the form for the related model
  await buildRelatedForm(relatedModel, modalCounter);
}

async function inferColumns(model) {
  const r = await fetch(`/admin/${model}/schema`, { credentials: 'include' });
  if (!r.ok) return { columns: [], foreign_keys: {} };
  const s = await r.json();
  const pk = s.primary_key;
  return {
    columns: s.columns.filter(c => c.name !== pk && !c.server_default),
    foreign_keys: s.foreign_keys || {}
  };
}

function formatFieldLabel(fieldName) {
  return fieldName.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
}

async function createFormField(column, foreignKeys) {
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
    
    // Load options asynchronously and wait for completion
    const options = await loadForeignKeyOptions(window.__MODEL__, column.name);
    options.forEach(option => {
      const optionElement = document.createElement('option');
      optionElement.value = option.id;
      optionElement.textContent = option.display;
      select.appendChild(optionElement);
    });
    
    fkContainer.appendChild(select);
    
    // Add + button for creating new related records
    const addButton = document.createElement('button');
    addButton.type = 'button';
    addButton.className = 'add-related-btn';
    addButton.innerHTML = '+';
    addButton.title = `Adicionar novo ${foreignKeys[column.name].target_model}`;
    addButton.onclick = () => showCreateRelatedModal(foreignKeys[column.name].target_model, column.name, select);
    
    fkContainer.appendChild(addButton);
    fieldContainer.appendChild(fkContainer);
    
    // Mark this field as ready for value setting
    fieldContainer.setAttribute('data-field-ready', 'true');
    
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
    
    // Mark this field as ready for value setting
    fieldContainer.setAttribute('data-field-ready', 'true');
  }
  
  return fieldContainer;
}

async function buildRelatedForm(model, modalCounter) {
  const { columns, foreign_keys } = await inferColumns(model);
  const form = document.getElementById(`modal-form-${modalCounter}`);
  if (!form) return;
  
  form.innerHTML = '';
  
  for (const column of columns) {
    const fieldElement = await createFormField(column, foreign_keys);
    form.appendChild(fieldElement);
  }
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
      } else if (el.value) {
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

async function loadItem() {
  console.log('=== loadItem() started ===');
  const model = window.__MODEL__;
  const id = window.__ITEM_ID__;
  console.log(`Loading item: model=${model}, id=${id}`);
  
  const schResp = await fetch(`/admin/${model}/schema`, { credentials: 'include' });
  const r = await fetch(`/admin/${model}/items/${id}`, { credentials: 'include' });
  const form = document.getElementById('edit-form');
  
  if (!r.ok || !schResp.ok) {
    console.error('Failed to load schema or item:', { schemaOk: schResp.ok, itemOk: r.ok });
    form.innerHTML = '<div class="error">Failed to load item</div>';
    return;
  }
  
  const schema = await schResp.json();
  const item = await r.json();
  console.log('Loaded schema:', schema);
  console.log('Loaded item:', item);
  
  form.innerHTML = '';
  
  // Filter columns to exclude primary key and server defaults
  const editableColumns = schema.columns.filter(col => 
    col.name !== schema.primary_key && !col.server_default
  );
  console.log('Editable columns:', editableColumns);
  
  // Create all form fields first (this will load foreign key options)
  console.log('=== Creating form fields ===');
  const fieldElements = [];
  for (const col of editableColumns) {
    console.log(`Creating field for column: ${col.name}, is_foreign_key: ${col.is_foreign_key}`);
    const fieldElement = await createFormField(col, schema.foreign_keys || {});
    fieldElements.push({ element: fieldElement, column: col });
    form.appendChild(fieldElement);
    console.log(`Field created for ${col.name}`);
  }
  
  console.log('=== Setting field values ===');
  // Now set the values after all fields are created and options are loaded
  for (const { element: fieldElement, column: col } of fieldElements) {
    const input = fieldElement.querySelector('input, select');
    console.log(`Setting value for ${col.name}: ${item[col.name]}`);
    
    if (input) {
      if (input.type === 'checkbox') {
        input.checked = item[col.name] || false;
        console.log(`Set checkbox ${col.name} to ${input.checked}`);
      } else if (input.type === 'datetime-local' && item[col.name]) {
        // Format datetime value for datetime-local input (remove seconds and timezone)
        const dateValue = new Date(item[col.name]);
        if (!isNaN(dateValue.getTime())) {
          // Format as YYYY-MM-DDTHH:MM
          const year = dateValue.getFullYear();
          const month = String(dateValue.getMonth() + 1).padStart(2, '0');
          const day = String(dateValue.getDate()).padStart(2, '0');
          const hours = String(dateValue.getHours()).padStart(2, '0');
          const minutes = String(dateValue.getMinutes()).padStart(2, '0');
          input.value = `${year}-${month}-${day}T${hours}:${minutes}`;
          console.log(`Set datetime ${col.name} to ${input.value}`);
        }
      } else {
        // For select elements (foreign keys), make sure the value exists in options
        if (input.tagName === 'SELECT' && item[col.name]) {
          console.log(`Setting SELECT ${col.name} with value ${item[col.name]}`);
          console.log('Available options:', Array.from(input.options).map(opt => ({ value: opt.value, text: opt.textContent })));
          
          const optionExists = Array.from(input.options).some(option => option.value == item[col.name]);
          if (optionExists) {
            input.value = item[col.name];
            console.log(`Successfully set SELECT ${col.name} to ${item[col.name]}`);
          } else {
            console.warn(`Option with value ${item[col.name]} not found for field ${col.name}`);
          }
        } else {
          input.value = item[col.name] ?? '';
          console.log(`Set input ${col.name} to ${input.value}`);
        }
      }
    } else {
      console.warn(`No input found for field ${col.name}`);
    }
  }
  console.log('=== loadItem() completed ===');
}

async function save() {
  const model = window.__MODEL__;
  const id = window.__ITEM_ID__;
  const form = document.getElementById('edit-form');
  const payload = {};
  
  Array.from(form.elements).forEach(el => {
    if (el.name) {
      if (el.type === 'checkbox') {
        payload[el.name] = el.checked;
      } else if (el.type === 'datetime-local' && el.value) {
        // Format datetime-local value to ISO string with seconds
        payload[el.name] = el.value + ':00';
      } else {
        payload[el.name] = el.value;
      }
    }
  });
  
  // Get access token from cookie
  const tokenCookie = document.cookie
    .split('; ')
    .find(row => row.startsWith('access_token='));
  const token = tokenCookie ? tokenCookie.split('=')[1] : null;
  
  const headers = { 'Content-Type': 'application/json' };
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }
  
  const r = await fetch(`/admin/${model}/items/${id}`, {
    method: 'PUT',
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
}

window.addEventListener('DOMContentLoaded', async () => {
  await loadItem();
  document.getElementById('save-btn').addEventListener('click', save);
});