#!/usr/bin/env python3
"""
Script to populate the database with test data for Empresa and other essential entities.
"""

import asyncio
import logging
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import engine
from app.db.models import (
    Empresa, CategoriaContrato, StatusAtivo, TipoAtivo, 
    AcessoAtivo, LocalInstalacao, StatusChamado, Prioridade,
    ChamadoCategoria, Funcao, Setor
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def create_test_data():
    """Create test data for the application."""
    
    async with AsyncSession(engine) as session:
        try:
            from sqlalchemy import select
            
            # Check if Empresas already exist
            existing_empresas = await session.scalar(select(Empresa).limit(1))
            if existing_empresas:
                logger.info("Empresa records already exist, skipping creation")
                return
            
            # Create test Empresas
            empresas = [
                Empresa(
                    nome="TechCorp Solutions",
                    cnpj="12.345.678/0001-90",
                    site="https://techcorp.com.br",
                    cidade="São Paulo",
                    endereço="Av. Paulista, 1000 - Bela Vista",
                    is_cliente=True
                ),
                Empresa(
                    nome="Inovação Digital Ltda",
                    cnpj="98.765.432/0001-10",
                    site="https://inovacaodigital.com.br",
                    cidade="Rio de Janeiro",
                    endereço="Rua das Flores, 500 - Copacabana",
                    is_cliente=True
                ),
                Empresa(
                    nome="Sistemas Avançados S.A.",
                    cnpj="11.222.333/0001-44",
                    site="https://sistemasavancados.com.br",
                    cidade="Belo Horizonte",
                    endereço="Rua da Tecnologia, 200 - Centro",
                    is_cliente=True
                ),
                Empresa(
                    nome="DataFlow Consultoria",
                    cnpj="55.666.777/0001-88",
                    site="https://dataflow.com.br",
                    cidade="Brasília",
                    endereço="SCS Quadra 1, Bloco A - Asa Sul",
                    is_cliente=True
                ),
                Empresa(
                    nome="CloudTech Serviços",
                    cnpj="99.888.777/0001-66",
                    site="https://cloudtech.com.br",
                    cidade="Porto Alegre",
                    endereço="Av. Ipiranga, 1500 - Centro Histórico",
                    is_cliente=True
                )
            ]
            
            for empresa in empresas:
                session.add(empresa)
            
            # Create test Categoria Contrato
            categorias_contrato = [
                CategoriaContrato(nome="Desenvolvimento de Software"),
                CategoriaContrato(nome="Consultoria em TI"),
                CategoriaContrato(nome="Suporte Técnico"),
                CategoriaContrato(nome="Infraestrutura"),
                CategoriaContrato(nome="Segurança da Informação")
            ]
            
            for categoria in categorias_contrato:
                session.add(categoria)
            
            # Create test Status Ativo
            status_ativos = [
                StatusAtivo(nome="Ativo"),
                StatusAtivo(nome="Inativo"),
                StatusAtivo(nome="Em Manutenção"),
                StatusAtivo(nome="Descartado")
            ]
            
            for status in status_ativos:
                session.add(status)
            
            # Create test Tipo Ativo
            tipos_ativo = [
                TipoAtivo(nome="Servidor"),
                TipoAtivo(nome="Workstation"),
                TipoAtivo(nome="Notebook"),
                TipoAtivo(nome="Switch"),
                TipoAtivo(nome="Roteador"),
                TipoAtivo(nome="Firewall"),
                TipoAtivo(nome="Impressora")
            ]
            
            for tipo in tipos_ativo:
                session.add(tipo)
            
            # Create test Acesso Ativo
            acessos_ativo = [
                AcessoAtivo(nome="Físico"),
                AcessoAtivo(nome="Remoto"),
                AcessoAtivo(nome="VPN"),
                AcessoAtivo(nome="SSH"),
                AcessoAtivo(nome="RDP")
            ]
            
            for acesso in acessos_ativo:
                session.add(acesso)
            
            # Create test Local Instalação
            locais_instalacao = [
                LocalInstalacao(nome="Data Center Principal"),
                LocalInstalacao(nome="Escritório São Paulo"),
                LocalInstalacao(nome="Filial Rio de Janeiro"),
                LocalInstalacao(nome="Home Office"),
                LocalInstalacao(nome="Cliente - On-site")
            ]
            
            for local in locais_instalacao:
                session.add(local)
            
            # Create test Status Chamado
            status_chamados = [
                StatusChamado(nome="Aberto", descricao="Chamado recém criado", cor="#007bff", ativo=True),
                StatusChamado(nome="Em Andamento", descricao="Chamado sendo trabalhado", cor="#ffc107", ativo=True),
                StatusChamado(nome="Aguardando Cliente", descricao="Aguardando resposta do cliente", cor="#fd7e14", ativo=True),
                StatusChamado(nome="Resolvido", descricao="Chamado resolvido", cor="#28a745", ativo=True),
                StatusChamado(nome="Fechado", descricao="Chamado fechado", cor="#6c757d", ativo=True)
            ]
            
            for status in status_chamados:
                session.add(status)
            
            # Create test Prioridades
            prioridades = [
                Prioridade(nome="Baixa", sla_padrao_min=2880),  # 48 horas
                Prioridade(nome="Normal", sla_padrao_min=1440),  # 24 horas
                Prioridade(nome="Alta", sla_padrao_min=480),     # 8 horas
                Prioridade(nome="Crítica", sla_padrao_min=120),  # 2 horas
                Prioridade(nome="Emergência", sla_padrao_min=30) # 30 minutos
            ]
            
            for prioridade in prioridades:
                session.add(prioridade)
            
            # Create test Chamado Categorias
            categorias_chamado = [
                ChamadoCategoria(nome="Hardware", descricao="Problemas relacionados a hardware", cor="#dc3545"),
                ChamadoCategoria(nome="Software", descricao="Problemas relacionados a software", cor="#007bff"),
                ChamadoCategoria(nome="Rede", descricao="Problemas de conectividade e rede", cor="#28a745"),
                ChamadoCategoria(nome="Segurança", descricao="Questões de segurança da informação", cor="#ffc107"),
                ChamadoCategoria(nome="Acesso", descricao="Problemas de acesso e permissões", cor="#6f42c1")
            ]
            
            for categoria in categorias_chamado:
                session.add(categoria)
            
            # Create test Funções
            funcoes = [
                Funcao(nome="Administrador de Sistema"),
                Funcao(nome="Desenvolvedor"),
                Funcao(nome="Analista de Suporte"),
                Funcao(nome="Gerente de TI"),
                Funcao(nome="Técnico de Rede"),
                Funcao(nome="DBA"),
                Funcao(nome="Analista de Segurança")
            ]
            
            for funcao in funcoes:
                session.add(funcao)
            
            # Create test Setores
            setores = [
                Setor(nome="TI"),
                Setor(nome="Desenvolvimento"),
                Setor(nome="Suporte"),
                Setor(nome="Infraestrutura"),
                Setor(nome="Segurança"),
                Setor(nome="Administração"),
                Setor(nome="Comercial")
            ]
            
            for setor in setores:
                session.add(setor)
            
            await session.commit()
            logger.info("Test data created successfully!")
            
            # Count records
            from sqlalchemy import select, func
            
            empresa_count = await session.scalar(select(func.count(Empresa.id)))
            logger.info(f"Created {empresa_count} Empresa records")
            
        except Exception as e:
            logger.error(f"Error creating test data: {e}")
            await session.rollback()
            raise


if __name__ == "__main__":
    asyncio.run(create_test_data())