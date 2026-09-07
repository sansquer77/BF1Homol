"""
Gerenciador de Usuário Master
Cria automaticamente na primeira execução
Versão 3.0 com melhoramentos de segurança
"""

import os
import logging
from typing import Optional, TypedDict
from db.connection_pool import get_pool
from db.repo_users import hash_password
from utils.logging_utils import redact_identifier

logger = logging.getLogger(__name__)


class MasterCredentials(TypedDict):
    nome: str
    email: str
    senha: str
    telegram: Optional[str]

class MasterUserManager:
    """
    Gerencia a criação automática do usuário Master
    Lê credenciais das variáveis de ambiente (Digital Ocean)
    """
    
    # Nomes das variáveis de ambiente (suporta maiúsculas e minúsculas)
    ENV_VAR_NOME = ['USUARIO_MASTER', 'usuario_master']
    ENV_VAR_EMAIL = ['EMAIL_MASTER', 'email_master']
    ENV_VAR_SENHA = ['SENHA_MASTER', 'senha_master']
    ENV_VAR_TELEGRAM = ['TELEGRAM_ADMIN', 'telegram_admin']  # Opcional
    
    @staticmethod
    def _get_env_value(keys: list, source: dict) -> Optional[str]:
        """Busca valor em múltiplas chaves (maiúscula/minúscula)"""
        for key in keys:
            value = source.get(key)
            if value:
                return value
        return None
    
    @staticmethod
    def _get_credentials() -> Optional[MasterCredentials]:
        """
        Obtém credenciais do Master a partir de variáveis de ambiente

        Fonte de busca:
        1. os.environ (Digital Ocean, Local com .env)
        
        Suporta variáveis em MAIÚsCULAS ou minúsculas.
        
        Returns:
            Dict com credenciais ou None se não encontradas
        """
        try:
            # Variáveis de ambiente (Digital Ocean App Platform)
            env_dict = dict(os.environ)
            nome = MasterUserManager._get_env_value(MasterUserManager.ENV_VAR_NOME, env_dict)
            email = MasterUserManager._get_env_value(MasterUserManager.ENV_VAR_EMAIL, env_dict)
            senha = MasterUserManager._get_env_value(MasterUserManager.ENV_VAR_SENHA, env_dict)
            
            if nome and email and senha:
                return {
                    'nome': nome,
                    'email': email,
                    'senha': senha,
                    'telegram': MasterUserManager._get_env_value(MasterUserManager.ENV_VAR_TELEGRAM, env_dict)
                }
            
            return None
            
        except Exception as e:
            logger.error(f"Erro ao obter credenciais do Master: {e}")
            return None
    
    @staticmethod
    def _master_exists() -> bool:
        """Verifica se já existe um usuário Master no banco"""
        try:
            with get_pool().get_connection() as conn:
                cur = conn.cursor()
                cur.execute("SELECT 1 FROM usuarios WHERE lower(trim(perfil))='master' LIMIT 1")
                return cur.fetchone() is not None
        except Exception as e:
            logger.warning(f"Erro ao verificar existência do Master: {e}")
            return False
    
    @staticmethod
    def _create_master() -> bool:
        """
        Cria usuário Master se não existir
        
        Fluxo:
        1. Lê variáveis de ambiente
        2. Verifica se já existe
        3. Cria com senha bcrypt
        4. Log a ação
        
        Returns:
            bool: True se criou, False se já existia ou erro
        """
        # Verificar se já existe
        if MasterUserManager._master_exists():
            logger.info("✓ Usuário Master já existe no banco de dados")
            return True

        # Em banco sem Master, configuração incompleta deve falhar fechada.
        creds = MasterUserManager._get_credentials()
        if not creds:
            raise RuntimeError(
                "Banco sem usuário Master: EMAIL_MASTER, SENHA_MASTER e USUARIO_MASTER são obrigatórios."
            )
        
        # Criar Master
        try:
            pool = get_pool()
            with pool.get_connection() as conn:
                cursor = conn.cursor()
                # Serializa bootstraps concorrentes do mesmo aplicativo.
                cursor.execute("SELECT pg_advisory_xact_lock(42463100)")
                cursor.execute("SELECT 1 FROM usuarios WHERE lower(trim(perfil))='master' LIMIT 1")
                if cursor.fetchone() is not None:
                    conn.commit()
                    return True
                
                # Hash da senha com bcrypt
                senha_hashed = hash_password(creds['senha'])
                
                # Insert com email do ambiente (não o email padrão)
                cursor.execute('''
                    INSERT INTO usuarios
                    (nome, email, senha_hash, perfil, status, faltas)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    RETURNING id
                ''', (
                    creds['nome'],
                    creds['email'],
                    senha_hashed,
                    'master',
                    'Ativo',
                    0
                ))

                inserted = cursor.fetchone()
                master_id = inserted['id'] if inserted else None
                
                conn.commit()
                
                logger.info(f"✓ Usuário Master criado com sucesso (ID: {master_id})")
                logger.info(f"  Nome: {creds['nome']}")
                logger.info("  Email: %s", redact_identifier(creds['email']))
                
                return True
                
        except Exception:
            logger.exception("✗ Erro ao criar usuário Master")
            raise
    
    @staticmethod
    def create_master_user() -> bool:
        """
        Método público para criar usuário Master na inicialização
        
        Returns:
            bool: True se criou ou já existe, False se erro
        """
        return MasterUserManager._create_master()
