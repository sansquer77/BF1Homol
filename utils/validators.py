from typing import Tuple


def validar_email(email: str) -> Tuple[bool, str]:
    """Valida formato de email"""
    import re
    
    if not email or len(email) > 254:
        return False, "Email inválido"
    
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    if not re.match(pattern, email):
        return False, "Email inválido"
    
    return True, ""


def validar_senha(senha: str) -> Tuple[bool, str]:
    """Valida força de senha"""
    if not senha:
        return False, "Senha obrigatória"
    
    if len(senha) < 8:
        return False, "Mínimo 8 caracteres"
    
    if not any(c.isupper() for c in senha):
        return False, "Deve conter maiúscula"
    
    if not any(c.isdigit() for c in senha):
        return False, "Deve conter número"
    
    return True, ""


def validar_id(value: int) -> Tuple[bool, str]:
    """Valida ID positivo"""
    try:
        id_val = int(value)
        if id_val <= 0:
            return False, "ID deve ser positivo"
        return True, ""
    except:
        return False, "ID inválido"
