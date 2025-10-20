#!/usr/bin/env python3
"""
Script to create test data for foreign key tables.
This will populate the lookup tables needed for the admin interface.
"""

import asyncio
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import SessionLocal
from app.db.models import (
    Empresa, CategoriaContrato, StatusAtivo, TipoAtivo, 
    AcessoAtivo, LocalInstalacao, Contrato, Contato, Funcao, Setor
)


async def create_test_data():
    """Create test data for foreign key tables."""
    async with SessionLocal() as session:
        try:
            print("Creating test data...")
            
            # Create Empresas
            empresas_data = [
                {"nome": "Empresa Cliente A", "cnpj": "11.111.111/0001-11", "is_cliente": True},
                {"nome": "Empresa Cliente B", "cnpj": "22.222.222/0001-22", "is_cliente": True},
                {"nome": "Fornecedor XYZ", "cnpj": "33.333.333/0001-33", "is_cliente": False},
                {"nome": "Parceiro ABC", "cnpj": "44.444.444/0001-44", "is_cliente": False},
            ]
            
            empresas = []
            for emp_data in empresas_data:
                empresa = Empresa(**emp_data)
                session.add(empresa)
                empresas.append(empresa)
            
            await session.flush()  # Get IDs
            print(f"Created {len(empresas)} empresas")
            
            # Create Funcoes
            funcoes_data = [
                {"nome": "Gerente"},
                {"nome": "Técnico"},
                {"nome": "Analista"},
                {"nome": "Coordenador"},
                {"nome": "Diretor"},
            ]
            
            funcoes = []
            for func_data in funcoes_data:
                funcao = Funcao(**func_data)
                session.add(funcao)
                funcoes.append(funcao)
            
            await session.flush()
            print(f"Created {len(funcoes)} funcoes")
            
            # Create Setores
            setores_data = [
                {"nome": "TI"},
                {"nome": "Operações"},
                {"nome": "Manutenção"},
                {"nome": "Comercial"},
                {"nome": "Administrativo"},
            ]
            
            setores = []
            for setor_data in setores_data:
                setor = Setor(**setor_data)
                session.add(setor)
                setores.append(setor)
            
            await session.flush()
            print(f"Created {len(setores)} setores")
            
            # Create Contatos
            contatos_data = [
                {"nome": "João Silva", "email": "joao@empresaa.com", "telefone": "(11) 99999-1111", "empresa_id": empresas[0].id, "funcao_id": funcoes[0].id, "setor_id": setores[0].id},
                {"nome": "Maria Santos", "email": "maria@empresab.com", "telefone": "(11) 99999-2222", "empresa_id": empresas[1].id, "funcao_id": funcoes[1].id, "setor_id": setores[1].id},
                {"nome": "Pedro Costa", "email": "pedro@fornecedor.com", "telefone": "(11) 99999-3333", "empresa_id": empresas[2].id, "funcao_id": funcoes[2].id, "setor_id": setores[2].id},
                {"nome": "Ana Oliveira", "email": "ana@parceiro.com", "telefone": "(11) 99999-4444", "empresa_id": empresas[3].id, "funcao_id": funcoes[3].id, "setor_id": setores[3].id},
            ]
            
            contatos = []
            for cont_data in contatos_data:
                contato = Contato(**cont_data)
                session.add(contato)
                contatos.append(contato)
            
            await session.flush()
            print(f"Created {len(contatos)} contatos")
            
            # Create Categoria Contratos
            categorias_data = [
                {"nome": "Manutenção Preventiva"},
                {"nome": "Manutenção Corretiva"},
                {"nome": "Instalação"},
                {"nome": "Consultoria"},
                {"nome": "Suporte Técnico"},
            ]
            
            categorias = []
            for cat_data in categorias_data:
                categoria = CategoriaContrato(**cat_data)
                session.add(categoria)
                categorias.append(categoria)
            
            await session.flush()
            print(f"Created {len(categorias)} categorias de contrato")
            
            # Create Contratos
            contratos_data = [
                {
                    "empresa_id": empresas[0].id,
                    "categoria_contrato_id": categorias[0].id,
                    "descricao": "Contrato de manutenção preventiva mensal",
                    "numero_pedido": "PED-001",
                    "duracao": "12 meses",
                    "fechamento": datetime.now() + timedelta(days=365),
                    "contratante_contato_id": contatos[0].id,
                    "responsavel_contato_id": contatos[1].id,
                    "concluido": False
                },
                {
                    "empresa_id": empresas[1].id,
                    "categoria_contrato_id": categorias[1].id,
                    "descricao": "Contrato de manutenção corretiva",
                    "numero_pedido": "PED-002",
                    "duracao": "6 meses",
                    "fechamento": datetime.now() + timedelta(days=180),
                    "contratante_contato_id": contatos[1].id,
                    "responsavel_contato_id": contatos[2].id,
                    "concluido": False
                },
                {
                    "empresa_id": empresas[2].id,
                    "categoria_contrato_id": categorias[2].id,
                    "descricao": "Contrato de instalação de equipamentos",
                    "numero_pedido": "PED-003",
                    "duracao": "3 meses",
                    "fechamento": datetime.now() + timedelta(days=90),
                    "contratante_contato_id": contatos[2].id,
                    "responsavel_contato_id": contatos[3].id,
                    "concluido": False
                },
            ]
            
            contratos = []
            for cont_data in contratos_data:
                contrato = Contrato(**cont_data)
                session.add(contrato)
                contratos.append(contrato)
            
            await session.flush()
            print(f"Created {len(contratos)} contratos")
            
            # Create Status Ativo
            status_ativo_data = [
                {"nome": "Ativo"},
                {"nome": "Inativo"},
                {"nome": "Em Manutenção"},
                {"nome": "Aguardando Instalação"},
                {"nome": "Descartado"},
            ]
            
            status_ativos = []
            for status_data in status_ativo_data:
                status = StatusAtivo(**status_data)
                session.add(status)
                status_ativos.append(status)
            
            await session.flush()
            print(f"Created {len(status_ativos)} status de ativo")
            
            # Create Tipo Ativo
            tipos_ativo_data = [
                {"nome": "Equipamento de TI"},
                {"nome": "Equipamento Industrial"},
                {"nome": "Ferramenta"},
                {"nome": "Veículo"},
                {"nome": "Mobiliário"},
                {"nome": "Equipamento de Segurança"},
            ]
            
            tipos_ativo = []
            for tipo_data in tipos_ativo_data:
                tipo = TipoAtivo(**tipo_data)
                session.add(tipo)
                tipos_ativo.append(tipo)
            
            await session.flush()
            print(f"Created {len(tipos_ativo)} tipos de ativo")
            
            # Create Acesso Ativo
            acessos_data = [
                {"nome": "Público"},
                {"nome": "Restrito"},
                {"nome": "Confidencial"},
                {"nome": "Interno"},
            ]
            
            acessos = []
            for acesso_data in acessos_data:
                acesso = AcessoAtivo(**acesso_data)
                session.add(acesso)
                acessos.append(acesso)
            
            await session.flush()
            print(f"Created {len(acessos)} tipos de acesso")
            
            # Create Local Instalacao
            locais_data = [
                {"nome": "Sala de Servidores"},
                {"nome": "Escritório Principal"},
                {"nome": "Fábrica - Linha 1"},
                {"nome": "Fábrica - Linha 2"},
                {"nome": "Almoxarifado"},
                {"nome": "Recepção"},
                {"nome": "Laboratório"},
            ]
            
            locais = []
            for local_data in locais_data:
                local = LocalInstalacao(**local_data)
                session.add(local)
                locais.append(local)
            
            await session.flush()
            print(f"Created {len(locais)} locais de instalação")
            
            # Commit all changes
            await session.commit()
            print("✅ Test data created successfully!")
            
        except Exception as e:
            await session.rollback()
            print(f"❌ Error creating test data: {e}")
            raise


if __name__ == "__main__":
    asyncio.run(create_test_data())