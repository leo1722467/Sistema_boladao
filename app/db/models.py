# app/db/models.py
from sqlalchemy import (
    Column, Integer, String, Text, DateTime, Boolean, ForeignKey, UniqueConstraint,
    JSON, BigInteger
)
from sqlalchemy.orm import relationship, Mapped, mapped_column
from sqlalchemy import text, MetaData
from app.db.base import Base
from sqlalchemy import UniqueConstraint

convention = {
    "ix": "ix__%(column_0_label)s",
    "uq": "uq__%(table_name)s__%(column_0_name)s",
    "ck": "ck__%(table_name)s__%(constraint_name)s",
    "fk": "fk__%(table_name)s__%(column_0_name)s__%(referred_table_name)s",
    "pk": "pk__%(table_name)s",
}

Base.metadata.naming_convention = convention


class TimestampMixin:
    criado_em: Mapped[DateTime] = mapped_column(
        DateTime, server_default=text("CURRENT_TIMESTAMP"), nullable=False
    )
    atualizado_em: Mapped[DateTime] = mapped_column(
        DateTime, server_default=text("CURRENT_TIMESTAMP"), nullable=False
    )


class Contato(Base, TimestampMixin):
    __tablename__ = "contato"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, index=True)
    nome: Mapped[str] = mapped_column(Text, nullable=False)
    email: Mapped[str | None] = mapped_column(Text)
    telefone: Mapped[str | None] = mapped_column(Text)
    empresa_id: Mapped[int | None] = mapped_column(ForeignKey("empresa.id"))
    funcao_id: Mapped[int | None] = mapped_column(ForeignKey("funcao.id"))
    setor_id: Mapped[int | None] = mapped_column(ForeignKey("setor.id"))
    is_user: Mapped[bool | None] = mapped_column(Boolean)
    ativo: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    empresa = relationship("Empresa", back_populates="contatos")
    funcao = relationship("Funcao", back_populates="contatos")
    setor = relationship("Setor", back_populates="contatos")
    auth = relationship("UserAuth", back_populates="contato", uselist=False)

    chamados_criados = relationship("Chamado", foreign_keys="Chamado.requisitante_contato_id", back_populates="requisitante")
    chamados_agente = relationship("Chamado", foreign_keys="Chamado.agente_contato_id", back_populates="agente")
    chamados_proprietario = relationship("Chamado", foreign_keys="Chamado.proprietario_contato_id", back_populates="proprietario")
    comentarios_chamado = relationship("ChamadoComentario", back_populates="contato")
    logs_chamado = relationship("ChamadoLog", back_populates="contato")


class UserAuth(Base, TimestampMixin):
    __tablename__ = "user_auth"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, index=True)
    contato_id: Mapped[int] = mapped_column(ForeignKey("contato.id"), nullable=False, unique=True)
    hashed_senha: Mapped[str] = mapped_column(Text, nullable=False)
    ativo: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    contato = relationship("Contato", back_populates="auth")
    logs = relationship("AuditLog", back_populates="usuario")


class AuditLog(Base):
    __tablename__ = "logs"

    id_log: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    id_usuario: Mapped[int] = mapped_column(ForeignKey("user_auth.id"), nullable=False)
    acao: Mapped[str] = mapped_column(Text, nullable=False)
    tabela_afetada: Mapped[str] = mapped_column(Text, nullable=False)
    registro_afetado: Mapped[int | None] = mapped_column(Integer)
    dados_anteriores: Mapped[dict | None] = mapped_column(JSON)
    dados_novos: Mapped[dict | None] = mapped_column(JSON)
    data_hora: Mapped[DateTime] = mapped_column(DateTime, server_default=text("CURRENT_TIMESTAMP"))
    detalhes_adicionais: Mapped[str | None] = mapped_column(Text)

    usuario = relationship("UserAuth", back_populates="logs")


class Empresa(Base, TimestampMixin):
    __tablename__ = "empresa"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, index=True)
    nome: Mapped[str] = mapped_column(Text, nullable=False)
    cnpj: Mapped[str | None] = mapped_column(Text)
    site: Mapped[str | None] = mapped_column(Text)
    cidade: Mapped[str | None] = mapped_column(Text)
    endereço: Mapped[str | None] = mapped_column("endereco", Text)
    is_cliente: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    contatos = relationship("Contato", back_populates="empresa")
    contratos = relationship("Contrato", back_populates="empresa")
    chamados = relationship("Chamado", back_populates="empresa")


class Funcao(Base):
    __tablename__ = "funcao"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    nome: Mapped[str] = mapped_column(Text, nullable=False, unique=True)

    contatos = relationship("Contato", back_populates="funcao")


class Setor(Base):
    __tablename__ = "setor"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    nome: Mapped[str] = mapped_column(Text, nullable=False, unique=True)

    contatos = relationship("Contato", back_populates="setor")


class CategoriaContrato(Base):
    __tablename__ = "categoria_contrato"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    nome: Mapped[str] = mapped_column(Text, nullable=False, unique=True)

    contratos = relationship("Contrato", back_populates="categoria")


class Contrato(Base, TimestampMixin):
    __tablename__ = "contrato"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, index=True)
    empresa_id: Mapped[int] = mapped_column(ForeignKey("empresa.id"), nullable=False)
    categoria_contrato_id: Mapped[int | None] = mapped_column(ForeignKey("categoria_contrato.id"))
    descricao: Mapped[str | None] = mapped_column(Text)
    numero_pedido: Mapped[str | None] = mapped_column(Text)
    duracao: Mapped[str | None] = mapped_column(Text)
    fechamento: Mapped[DateTime | None] = mapped_column(DateTime)
    contratante_contato_id: Mapped[int | None] = mapped_column(ForeignKey("contato.id"))
    responsavel_contato_id: Mapped[int | None] = mapped_column(ForeignKey("contato.id"))
    concluido: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    empresa = relationship("Empresa", back_populates="contratos")
    categoria = relationship("CategoriaContrato", back_populates="contratos")
    contratante = relationship("Contato", foreign_keys=[contratante_contato_id])
    responsavel = relationship("Contato", foreign_keys=[responsavel_contato_id])
    ativos = relationship("Ativo", back_populates="contrato")


class StatusAtivo(Base):
    __tablename__ = "status_ativo"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    nome: Mapped[str] = mapped_column(Text, nullable=False, unique=True)

    ativos = relationship("Ativo", back_populates="status")


class TipoAtivo(Base):
    __tablename__ = "tipo_ativo"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    nome: Mapped[str] = mapped_column(Text, nullable=False, unique=True)

    ativos = relationship("Ativo", back_populates="tipo")
    defeitos = relationship("ChamadoDefeito", back_populates="tipo_ativo")


class AcessoAtivo(Base):
    __tablename__ = "acesso_ativo"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    nome: Mapped[str] = mapped_column(Text, nullable=False, unique=True)

    ativos = relationship("Ativo", back_populates="acesso")


class ChamadoDefeito(Base):
    __tablename__ = "chamado_defeito"
    __table_args__ = (
        UniqueConstraint("tipo_ativo_id", "nome", name="uq_chamado_defeito_tipo_nome"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    nome: Mapped[str] = mapped_column(Text, nullable=False)
    tipo_ativo_id: Mapped[int] = mapped_column(ForeignKey("tipo_ativo.id"), nullable=False, index=True)

    tipo_ativo = relationship("TipoAtivo", back_populates="defeitos")


class LocalInstalacao(Base):
    __tablename__ = "local_instalacao"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    nome: Mapped[str] = mapped_column(Text, nullable=False, unique=True)

    ativos = relationship("Ativo", back_populates="local_instalacao")


class Ativo(Base):
    __tablename__ = "ativo"
    __table_args__ = (
        UniqueConstraint("empresa_id", "serial_text", name="uq_ativo_empresa_serial"),
    )

    id = mapped_column(Integer, primary_key=True, autoincrement=True, index=True)
    empresa_id = mapped_column(ForeignKey("empresa.id"), index=True, nullable=False)

    tag = mapped_column(Text, unique=True, nullable=True)
    descricao = mapped_column(Text, nullable=True)

    contrato_id = mapped_column(ForeignKey("contrato.id"), nullable=True)
    status_ativo_id = mapped_column(ForeignKey("status_ativo.id"), nullable=True)
    tipo_ativo_id = mapped_column(ForeignKey("tipo_ativo.id"), nullable=True)
    acesso_ativo_id = mapped_column(ForeignKey("acesso_ativo.id"), nullable=True)
    local_instalacao_id = mapped_column(ForeignKey("local_instalacao.id"), nullable=True)

    interno = mapped_column(Boolean, nullable=True)
    periodicidade = mapped_column(Text, nullable=True)
    data_instalacao = mapped_column(DateTime, nullable=True)

    # novo vínculo 1:1 com estoque
    stock_unit_id = mapped_column(ForeignKey("estoque.id", ondelete="SET NULL"), unique=True, nullable=True)

    # novo serial textual, único por empresa
    serial_text = mapped_column(Text, nullable=False)

    criado_em = mapped_column(DateTime, server_default=text("CURRENT_TIMESTAMP"), nullable=True)

    # relationships (ajuste nomes conforme seu padrão):
    empresa = relationship("Empresa")
    contrato = relationship("Contrato", back_populates="ativos")
    status = relationship("StatusAtivo", back_populates="ativos")
    tipo = relationship("TipoAtivo", back_populates="ativos")
    acesso = relationship("AcessoAtivo", back_populates="ativos")
    local_instalacao = relationship("LocalInstalacao", back_populates="ativos")
    estoque_item = relationship("Estoque", foreign_keys=[stock_unit_id], uselist=False)

class TipoOS(Base):
    __tablename__ = "tipo_os"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    nome: Mapped[str] = mapped_column(Text, nullable=False, unique=True)

    ordens_servico = relationship("OrdemServico", back_populates="tipo")

class OrdemServicoChamado(Base):
    __tablename__ = "ordem_servico_chamado"
    ordem_servico_id = mapped_column(ForeignKey("ordem_servico.id", ondelete="CASCADE"), primary_key=True)
    chamado_id = mapped_column(ForeignKey("chamado.id", ondelete="CASCADE"), primary_key=True)

class OrdemServico(Base):
    __tablename__ = "ordem_servico"
    chamados = relationship(
        "Chamado",
        secondary="ordem_servico_chamado",
        backref="ordens_servico_n_n",
        lazy="selectin",
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, index=True)
    numero_os: Mapped[str | None] = mapped_column(Text, unique=True)
    chamado_id: Mapped[int | None] = mapped_column(ForeignKey("chamado.id"))
    data_hora_inicio: Mapped[DateTime | None] = mapped_column(DateTime)
    data_hora_fim: Mapped[DateTime | None] = mapped_column(DateTime)
    duracao: Mapped[str | None] = mapped_column(Text)
    atividades_realizadas: Mapped[str | None] = mapped_column(Text)
    observacao: Mapped[str | None] = mapped_column(Text)
    numero_apr: Mapped[str | None] = mapped_column(Text)
    tipo_os_id: Mapped[int | None] = mapped_column(ForeignKey("tipo_os.id"))

    tipo = relationship("TipoOS", back_populates="ordens_servico")
    chamado = relationship("Chamado", back_populates="ordens_servico", foreign_keys=[chamado_id])


class Foto(Base):
    __tablename__ = "foto"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tabela_nome: Mapped[str | None] = mapped_column(Text)
    tabela_id: Mapped[int | None] = mapped_column(Integer)
    tipo: Mapped[str | None] = mapped_column(Text)
    arquivo_url: Mapped[str | None] = mapped_column(Text)
    tecnico_usuario_id: Mapped[int | None] = mapped_column(Integer)
    criado_em: Mapped[DateTime | None] = mapped_column(DateTime, server_default=text("CURRENT_TIMESTAMP"))
    ordem: Mapped[int | None] = mapped_column(Integer)


class Fabricante(Base):
    __tablename__ = "fabricante"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    nome: Mapped[str] = mapped_column(Text, nullable=False, unique=True)

    catalogo = relationship("CatalogoPeca", back_populates="fabricante")


class CategoriaPeca(Base):
    __tablename__ = "categoria_peca"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    nome: Mapped[str] = mapped_column(Text, nullable=False, unique=True)


class StatusEstoque(Base):
    __tablename__ = "status_estoque"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    nome: Mapped[str] = mapped_column(Text, nullable=False, unique=True)


class UnidadeMedida(Base):
    __tablename__ = "unidade_medida"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    nome: Mapped[str] = mapped_column(Text, nullable=False, unique=True)


class TipoMovimentacao(Base):
    __tablename__ = "tipo_movimentacao"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    nome: Mapped[str] = mapped_column(Text, nullable=False, unique=True)


class CatalogoPeca(Base):
    __tablename__ = "catalogo_peca"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, index=True)
    nome: Mapped[str] = mapped_column(Text, nullable=False)
    modelo: Mapped[str | None] = mapped_column(Text)
    fabricante_id: Mapped[int | None] = mapped_column(ForeignKey("fabricante.id"))
    unidade_medida_id: Mapped[int | None] = mapped_column(ForeignKey("unidade_medida.id"))
    fornecedor_empresa_id: Mapped[int | None] = mapped_column(ForeignKey("empresa.id"))
    data_criacao: Mapped[DateTime | None] = mapped_column(DateTime, server_default=text("CURRENT_TIMESTAMP"))
    url_foto_id: Mapped[int | None] = mapped_column(ForeignKey("foto.id"))

    fabricante = relationship("Fabricante", back_populates="catalogo")
    unidade_medida = relationship("UnidadeMedida")
    fornecedor = relationship("Empresa")
    foto = relationship("Foto")
    itens_estoque = relationship("Estoque", back_populates="catalogo")


class Estoque(Base):
    __tablename__ = "estoque"
    __table_args__ = (
        UniqueConstraint("empresa_id", "serial", name="uq_estoque_empresa_serial"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, index=True)
    catalogo_peca_id: Mapped[int] = mapped_column(ForeignKey("catalogo_peca.id"), nullable=False)
    serial: Mapped[str | None] = mapped_column(Text)
    status_estoque_id: Mapped[int | None] = mapped_column(ForeignKey("status_estoque.id"))
    novo: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    recondicionado_em: Mapped[DateTime | None] = mapped_column(DateTime)
    qtd: Mapped[int | None] = mapped_column(Integer)
    empresa_id: Mapped[int | None] = mapped_column(ForeignKey("empresa.id"))
    vinculado_ativo_id: Mapped[int | None] = mapped_column(ForeignKey("ativo.id"))

    catalogo = relationship("CatalogoPeca", back_populates="itens_estoque")
    status = relationship("StatusEstoque")
    empresa = relationship("Empresa")
    ativo = relationship("Ativo", foreign_keys=[vinculado_ativo_id])
    movimentacoes = relationship("MovimentacaoEstoque", back_populates="estoque")


class MovimentacaoEstoque(Base):
    __tablename__ = "movimentacao_estoque"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    estoque_id: Mapped[int] = mapped_column(ForeignKey("estoque.id"), nullable=False)
    tipo_movimentacao_id: Mapped[int] = mapped_column(ForeignKey("tipo_movimentacao.id"), nullable=False)
    data_movimentacao: Mapped[DateTime | None] = mapped_column(DateTime, server_default=text("CURRENT_TIMESTAMP"))
    origem_status_estoque_id: Mapped[int | None] = mapped_column(ForeignKey("status_estoque.id"))
    destino_status_estoque_id: Mapped[int | None] = mapped_column(ForeignKey("status_estoque.id"))
    observacao: Mapped[str | None] = mapped_column(Text)
    quantidade: Mapped[int | None] = mapped_column(Integer)
    user_auth_id: Mapped[int | None] = mapped_column(ForeignKey("user_auth.id"))
    numero_ordem_servico_id: Mapped[int | None] = mapped_column(ForeignKey("ordem_servico.id"))
    origem_ativo_id: Mapped[int | None] = mapped_column(ForeignKey("ativo.id"))
    destino_ativo_id: Mapped[int | None] = mapped_column(ForeignKey("ativo.id"))

    estoque = relationship("Estoque", back_populates="movimentacoes")
    tipo_movimentacao = relationship("TipoMovimentacao")
    origem_status = relationship("StatusEstoque", foreign_keys=[origem_status_estoque_id])
    destino_status = relationship("StatusEstoque", foreign_keys=[destino_status_estoque_id])
    usuario = relationship("UserAuth")
    os = relationship("OrdemServico")
    origem_ativo = relationship("Ativo", foreign_keys=[origem_ativo_id])
    destino_ativo = relationship("Ativo", foreign_keys=[destino_ativo_id])


class Procedimento(Base):
    __tablename__ = "procedimento"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tipo_procedimento: Mapped[str | None] = mapped_column(Text)
    categoria_peca_id: Mapped[int | None] = mapped_column(ForeignKey("categoria_peca.id"))

    etapas = relationship("EtapaProcedimento", back_populates="procedimento")


class EtapaProcedimento(Base):
    __tablename__ = "etapas_procedimento"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    nome: Mapped[str] = mapped_column(Text, nullable=False)
    procedimento_id: Mapped[int] = mapped_column(ForeignKey("procedimento.id"))
    descricao: Mapped[str | None] = mapped_column(Text)
    ordem: Mapped[int | None] = mapped_column(Integer)

    procedimento = relationship("Procedimento", back_populates="etapas")


class SetorAtuacaoCliente(Base):
    __tablename__ = "setor_atuacao_cliente"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    cliente_empresa_id: Mapped[int | None] = mapped_column(ForeignKey("empresa.id"))
    nome: Mapped[str] = mapped_column(Text, nullable=False)
    descricao: Mapped[str | None] = mapped_column(Text)
    categoria_contrato: Mapped[str | None] = mapped_column(Text)
    responsavel_area: Mapped[str | None] = mapped_column(Text)


class CategoriaSetor(Base):
    __tablename__ = "categoria_setor"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    nome: Mapped[str] = mapped_column(Text, nullable=False)
    riscos_apr_id: Mapped[int | None] = mapped_column(ForeignKey("riscos_apr.id"))


class RiscosAPR(Base):
    __tablename__ = "riscos_apr"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    nome: Mapped[str] = mapped_column(Text, nullable=False)
    categoria_id: Mapped[int | None] = mapped_column(ForeignKey("categoria_setor.id"))
    medidas_controle_apr_id: Mapped[int | None] = mapped_column(ForeignKey("medidas_controle_apr.id"))

    categoria = relationship("CategoriaSetor", foreign_keys=[categoria_id])
    medidas_controle = relationship("MedidasControleAPR", foreign_keys=[medidas_controle_apr_id])
    riscos_ocupacionais = relationship("RiscosOcupacionaisAPR", back_populates="riscos_apr")
    riscos_ambientais = relationship("RiscosAmbientaisAPR", back_populates="riscos_apr")


class MedidasControleAPR(Base):
    __tablename__ = "medidas_controle_apr"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    nome: Mapped[str] = mapped_column(Text, nullable=False)
    descricao: Mapped[str | None] = mapped_column(Text)
    categoria_id: Mapped[int | None] = mapped_column(ForeignKey("categoria_setor.id"))
    epi_apr_id: Mapped[int | None] = mapped_column(ForeignKey("epi_apr.id"))


class AtividadeAPR(Base):
    __tablename__ = "atividade_apr"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    riscos_apr_id: Mapped[int | None] = mapped_column(ForeignKey("riscos_apr.id"))
    medidas_controle_apr_id: Mapped[int | None] = mapped_column(ForeignKey("medidas_controle_apr.id"))
    descricao: Mapped[str | None] = mapped_column(Text)
    metodo_acesso_apr_id: Mapped[int | None] = mapped_column(ForeignKey("metodo_acesso_apr.id"))


class EPIAPR(Base):
    __tablename__ = "epi_apr"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    nome: Mapped[str] = mapped_column(Text, nullable=False)
    medidas_controle_apr_id: Mapped[int | None] = mapped_column(ForeignKey("medidas_controle_apr.id"))


class TipoAtividadeAPR(Base):
    __tablename__ = "tipo_atividade_apr"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    nome: Mapped[str] = mapped_column(Text, nullable=False, unique=True)


class TipoDeslocamento(Base):
    __tablename__ = "tipo_deslocamento"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    nome: Mapped[str] = mapped_column(Text, nullable=False, unique=True)


class FrequenciaAtividadeAPR(Base):
    __tablename__ = "frequencia_atividade_apr"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    nome: Mapped[str] = mapped_column(Text, nullable=False, unique=True)


class SistemaProtecaoQuedasAPR(Base):
    __tablename__ = "sistema_protecao_quedas_apr"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    nome: Mapped[str] = mapped_column(Text, nullable=False, unique=True)


class MetodoAcessoAPR(Base):
    __tablename__ = "metodo_acesso_apr"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    nome: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    sistema_protecao_quedas_id: Mapped[int | None] = mapped_column(ForeignKey("sistema_protecao_quedas_apr.id"))


class EnergiasAPR(Base):
    __tablename__ = "energias_apr"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    nome: Mapped[str] = mapped_column(Text, nullable=False, unique=True)


class RiscosOcupacionaisAPR(Base):
    __tablename__ = "riscos_ocupacionais_apr"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    riscos_apr_id: Mapped[int] = mapped_column(ForeignKey("riscos_apr.id"))
    nome: Mapped[str] = mapped_column(Text, nullable=False)

    riscos_apr = relationship("RiscosAPR", back_populates="riscos_ocupacionais")


class RiscosAmbientaisAPR(Base):
    __tablename__ = "riscos_ambientais_apr"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    riscos_apr_id: Mapped[int] = mapped_column(ForeignKey("riscos_apr.id"))
    nome: Mapped[str] = mapped_column(Text, nullable=False)

    riscos_apr = relationship("RiscosAPR", back_populates="riscos_ambientais")


class APR(Base, TimestampMixin):
    __tablename__ = "apr"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, index=True)
    cliente_empresa_id: Mapped[int | None] = mapped_column(ForeignKey("empresa.id"))
    setor_atuacao_cliente_id: Mapped[int | None] = mapped_column(ForeignKey("setor_atuacao_cliente.id"))
    atividade_apr_id: Mapped[int | None] = mapped_column(ForeignKey("atividade_apr.id"))
    tipo_atividade_apr_id: Mapped[int | None] = mapped_column(ForeignKey("tipo_atividade_apr.id"))
    tipo_deslocamento_id: Mapped[int | None] = mapped_column(ForeignKey("tipo_deslocamento.id"))
    frequencia_atividade_apr_id: Mapped[int | None] = mapped_column(ForeignKey("frequencia_atividade_apr.id"))
    metodo_acesso_apr_id: Mapped[int | None] = mapped_column(ForeignKey("metodo_acesso_apr.id"))
    sistema_protecao_quedas_id: Mapped[int | None] = mapped_column(ForeignKey("sistema_protecao_quedas_apr.id"))
    data_emissao: Mapped[DateTime | None] = mapped_column(DateTime)
    versao: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str | None] = mapped_column(Text)
    responsavel_elaboracao: Mapped[str | None] = mapped_column(Text)
    responsavel_area: Mapped[str | None] = mapped_column(Text)
    responsavavel_execucao: Mapped[str | None] = mapped_column(Text)
    aprovador: Mapped[str | None] = mapped_column(Text)
    local_execucao: Mapped[str | None] = mapped_column(Text)
    descricao_atividade: Mapped[str | None] = mapped_column(Text)
    objetivos: Mapped[str | None] = mapped_column(Text)
    data_inicio_prevista: Mapped[DateTime | None] = mapped_column(DateTime)
    data_fim_prevista: Mapped[DateTime | None] = mapped_column(DateTime)
    validade_ate: Mapped[DateTime | None] = mapped_column(DateTime)
    metodo_matriz_risco: Mapped[str | None] = mapped_column(Text)
    observacoes: Mapped[str | None] = mapped_column(Text)


class StatusChamado(Base):
    __tablename__ = "status_chamado"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, index=True)
    nome: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    descricao: Mapped[str | None] = mapped_column(Text)
    cor: Mapped[str | None] = mapped_column(Text)
    ativo: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    chamados = relationship("Chamado", back_populates="status")


class Prioridade(Base):
    __tablename__ = "prioridade"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, index=True)
    nome: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    sla_padrao_min: Mapped[int | None] = mapped_column(Integer)

    chamados = relationship("Chamado", back_populates="prioridade")


class ChamadoCategoria(Base):
    __tablename__ = "chamado_categoria"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, index=True)
    nome: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    descricao: Mapped[str | None] = mapped_column(Text)
    cor: Mapped[str | None] = mapped_column(Text)

    chamados = relationship("Chamado", back_populates="categoria")


class Chamado(Base):
    __tablename__ = "chamado"
    __table_args__ = (
        UniqueConstraint("empresa_id", "numero", name="uq_chamado_empresa_numero"),
    )
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, index=True)
    numero: Mapped[str] = mapped_column(Text, nullable=False)
    origem: Mapped[str | None] = mapped_column(Text, nullable=True)
    empresa_id: Mapped[int | None] = mapped_column(ForeignKey("empresa.id"))
    titulo: Mapped[str] = mapped_column(Text, nullable=False)
    descricao: Mapped[str | None] = mapped_column(Text)
    status_id: Mapped[int | None] = mapped_column(ForeignKey("status_chamado.id"))
    prioridade_id: Mapped[int | None] = mapped_column(ForeignKey("prioridade.id"))
    ultima_atualizacao: Mapped[DateTime | None] = mapped_column(DateTime)
    requisitante_contato_id: Mapped[int | None] = mapped_column(ForeignKey("contato.id"))
    agente_contato_id: Mapped[int | None] = mapped_column(ForeignKey("contato.id"))
    proprietario_contato_id: Mapped[int | None] = mapped_column(ForeignKey("contato.id"))
    categoria_id: Mapped[int | None] = mapped_column(ForeignKey("chamado_categoria.id"))
    ativo_id: Mapped[int | None] = mapped_column(ForeignKey("ativo.id"))
    criado_em: Mapped[DateTime] = mapped_column(DateTime, server_default=text("CURRENT_TIMESTAMP"), nullable=False)
    atualizado_em: Mapped[DateTime] = mapped_column(DateTime, server_default=text("CURRENT_TIMESTAMP"), nullable=False)
    fechado_em: Mapped[DateTime | None] = mapped_column(DateTime)
    origem_os_pendencia_id: Mapped[int | None] = mapped_column(ForeignKey("ordem_servico.id"))

    empresa = relationship("Empresa", back_populates="chamados")
    requisitante = relationship("Contato", foreign_keys=[requisitante_contato_id], back_populates="chamados_criados")
    agente = relationship("Contato", foreign_keys=[agente_contato_id], back_populates="chamados_agente")
    proprietario = relationship("Contato", foreign_keys=[proprietario_contato_id], back_populates="chamados_proprietario")
    categoria = relationship("ChamadoCategoria", back_populates="chamados")
    prioridade = relationship("Prioridade", back_populates="chamados")
    status = relationship("StatusChamado", back_populates="chamados")
    comentarios = relationship("ChamadoComentario", back_populates="chamado", cascade="all, delete-orphan")
    logs = relationship("ChamadoLog", back_populates="chamado", cascade="all, delete-orphan")
    ativo = relationship("Ativo")
    ordens_servico = relationship("OrdemServico", back_populates="chamado", foreign_keys="OrdemServico.chamado_id")


class ChamadoComentario(Base):
    __tablename__ = "chamado_comentario"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, index=True)
    chamado_id: Mapped[int] = mapped_column(ForeignKey("chamado.id"), nullable=False)
    contato_id: Mapped[int | None] = mapped_column(ForeignKey("contato.id"))
    comentario: Mapped[str] = mapped_column(Text, nullable=False)
    data_hora: Mapped[DateTime] = mapped_column(DateTime, server_default=text("CURRENT_TIMESTAMP"), nullable=False)

    contato = relationship("Contato", back_populates="comentarios_chamado")
    chamado = relationship("Chamado", back_populates="comentarios")


class ChamadoLog(Base):
    __tablename__ = "chamado_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, index=True)
    chamado_id: Mapped[int] = mapped_column(ForeignKey("chamado.id"), nullable=False)
    contato_id: Mapped[int | None] = mapped_column(ForeignKey("contato.id"))
    id_alteracao: Mapped[str | None] = mapped_column(Text)
    data_hora: Mapped[DateTime] = mapped_column(DateTime, server_default=text("CURRENT_TIMESTAMP"), nullable=False)

    chamado = relationship("Chamado", back_populates="logs")
    contato = relationship("Contato", back_populates="logs_chamado")
class TicketSequence(Base):
    __tablename__ = "ticket_sequence"
    __table_args__ = (
        UniqueConstraint("empresa_id", "origin", name="uq_ticket_sequence_empresa_origin"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, index=True)
    empresa_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    origin: Mapped[str] = mapped_column(Text, nullable=False)
    next_value: Mapped[int] = mapped_column(Integer, nullable=False, default=1)


class TicketCounter(Base):
    __tablename__ = "ticket_counter"
    __table_args__ = (
        UniqueConstraint("empresa_id", name="uq_ticket_counter_empresa"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, index=True)
    empresa_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    next_value: Mapped[int] = mapped_column(Integer, nullable=False, default=1)


class HelpdeskRoutingRule(Base, TimestampMixin):
    __tablename__ = "helpdesk_routing_rule"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, index=True)
    empresa_id: Mapped[int] = mapped_column(ForeignKey("empresa.id"), nullable=False, index=True)
    categoria_id: Mapped[int | None] = mapped_column(ForeignKey("chamado_categoria.id"), index=True)
    prioridade_id: Mapped[int | None] = mapped_column(ForeignKey("prioridade.id"), index=True)
    agente_contato_id: Mapped[int | None] = mapped_column(ForeignKey("contato.id"))
    ativo: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class HelpdeskMacro(Base, TimestampMixin):
    __tablename__ = "helpdesk_macro"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, index=True)
    empresa_id: Mapped[int] = mapped_column(ForeignKey("empresa.id"), nullable=False, index=True)
    nome: Mapped[str] = mapped_column(Text, nullable=False)
    descricao: Mapped[str | None] = mapped_column(Text)
    actions: Mapped[dict | None] = mapped_column(JSON)


class HelpdeskSLAOverride(Base, TimestampMixin):
    __tablename__ = "helpdesk_sla_override"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, index=True)
    empresa_id: Mapped[int] = mapped_column(ForeignKey("empresa.id"), nullable=False, index=True)
    prioridade_id: Mapped[int] = mapped_column(ForeignKey("prioridade.id"), nullable=False, index=True)
    response_hours: Mapped[int] = mapped_column(Integer, nullable=False, default=24)
    resolution_hours: Mapped[int] = mapped_column(Integer, nullable=False, default=72)
    escalation_hours: Mapped[int] = mapped_column(Integer, nullable=False, default=48)


class HelpdeskAutoClosePolicy(Base, TimestampMixin):
    __tablename__ = "helpdesk_auto_close_policy"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, index=True)
    empresa_id: Mapped[int] = mapped_column(ForeignKey("empresa.id"), nullable=False, unique=True, index=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    pending_customer_days: Mapped[int] = mapped_column(Integer, nullable=False, default=14)
    resolved_days: Mapped[int] = mapped_column(Integer, nullable=False, default=7)


class KBCategory(Base, TimestampMixin):
    __tablename__ = "kb_category"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, index=True)
    empresa_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    nome: Mapped[str] = mapped_column(Text, nullable=False)
    descricao: Mapped[str | None] = mapped_column(Text)


class KBArticle(Base, TimestampMixin):
    __tablename__ = "kb_article"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, index=True)
    empresa_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    categoria_id: Mapped[int | None] = mapped_column(ForeignKey("kb_category.id"), index=True)
    titulo: Mapped[str] = mapped_column(Text, nullable=False)
    resumo: Mapped[str | None] = mapped_column(Text)
    conteudo: Mapped[str] = mapped_column(Text, nullable=False)
    tags: Mapped[dict | None] = mapped_column(JSON)
    publicado: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    visibilidade: Mapped[str] = mapped_column(Text, nullable=False, default="external")
