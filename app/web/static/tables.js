/* eslint-disable */
document.addEventListener('DOMContentLoaded', async () => {
  const container = document.getElementById('models');
  try {
    const res = await fetch('/admin/models', { credentials: 'include' });
    if (!res.ok) {
      container.innerHTML = `<p>Failed to load models: ${res.status}</p>`;
      return;
    }
    const models = await res.json();
    
    // Define logical groups
    const groups = {
      'Core System': ['Contato', 'UserAuth', 'AuditLog', 'Empresa', 'Funcao', 'Setor'],
      'Contracts & Assets': ['CategoriaContrato', 'Contrato', 'StatusAtivo', 'TipoAtivo', 'AcessoAtivo', 'LocalInstalacao', 'Ativo'],
      'Work Orders': ['TipoOS', 'OrdemServico', 'Foto'],
      'Inventory & Parts': ['Fabricante', 'CategoriaPeca', 'StatusEstoque', 'UnidadeMedida', 'TipoMovimentacao', 'CatalogoPeca', 'Estoque', 'MovimentacaoEstoque'],
      'Procedures': ['Procedimento', 'EtapaProcedimento'],
      'APR (Risk Assessment)': ['SetorAtuacaoCliente', 'CategoriaSetor', 'RiscosAPR', 'MedidasControleAPR', 'AtividadeAPR', 'EPIAPR', 'TipoAtividadeAPR', 'TipoDeslocamento', 'FrequenciaAtividadeAPR', 'SistemaProtecaoQuedasAPR', 'MetodoAcessoAPR', 'EnergiasAPR', 'RiscosOcupacionaisAPR', 'RiscosAmbientaisAPR'],
      'Support Tickets': ['StatusChamado', 'Prioridade', 'ChamadoCategoria', 'Chamado', 'ChamadoComentario', 'ChamadoLog', 'ChamadoDefeito']
    };
    
    // Create grouped sections
    Object.entries(groups).forEach(([groupName, groupModels]) => {
      const availableModels = groupModels.filter(model => models.includes(model));
      if (availableModels.length === 0) return;
      
      const section = document.createElement('div');
      section.className = 'model-group';
      
      const header = document.createElement('h3');
      header.textContent = groupName;
      header.className = 'group-header';
      section.appendChild(header);
      
      const list = document.createElement('ul');
      list.className = 'model-list';
      
      availableModels.forEach(model => {
        const li = document.createElement('li');
        li.className = 'model-item';
        li.innerHTML = `
          <span class="model-name">${model}</span>
          <div class="model-actions">
            <a href="/admin/${model}" class="action-link list-link">[list]</a>
            <a href="/admin/${model}/create" class="action-link create-link">[create]</a>
          </div>
        `;
        list.appendChild(li);
      });
      
      section.appendChild(list);
      container.appendChild(section);
    });
    
    // Add any ungrouped models
    const groupedModels = Object.values(groups).flat();
    const ungroupedModels = models.filter(model => !groupedModels.includes(model));
    
    if (ungroupedModels.length > 0) {
      const section = document.createElement('div');
      section.className = 'model-group';
      
      const header = document.createElement('h3');
      header.textContent = 'Other Models';
      header.className = 'group-header';
      section.appendChild(header);
      
      const list = document.createElement('ul');
      list.className = 'model-list';
      
      ungroupedModels.forEach(model => {
        const li = document.createElement('li');
        li.className = 'model-item';
        li.innerHTML = `
          <span class="model-name">${model}</span>
          <div class="model-actions">
            <a href="/admin/${model}" class="action-link list-link">[list]</a>
            <a href="/admin/${model}/create" class="action-link create-link">[create]</a>
          </div>
        `;
        list.appendChild(li);
      });
      
      section.appendChild(list);
      container.appendChild(section);
    }
    
  } catch (e) {
    container.innerHTML = `<p>Error: ${(e && e.message) || 'unknown'}</p>`;
  }
});
