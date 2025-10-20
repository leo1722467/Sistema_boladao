from typing import Optional
from pydantic import BaseModel, EmailStr


class ContatoOut(BaseModel):
    """Public representation of a Contato.

    Attributes:
        id: Unique identifier.
        nome: Full name.
        email: Email address.
        telefone: Phone number.
        ativo: Active flag.
    """

    id: int
    nome: str
    email: Optional[EmailStr]
    telefone: Optional[str]
    ativo: bool