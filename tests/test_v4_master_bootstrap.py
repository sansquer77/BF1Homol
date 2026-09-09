import os
import unittest
from unittest.mock import MagicMock, patch

from tests._db_driver_stub import install_if_needed

install_if_needed()

from db.master_user_manager import MasterUserManager


class MasterBootstrapV4Tests(unittest.TestCase):
    def test_existing_master_is_synchronized_from_environment_credentials(self):
        credentials = {"nome": "Master Env", "email": "master@example.invalid", "senha": "Secret-123", "telegram": None}
        cursor = MagicMock(); cursor.fetchone.return_value = {"id": 1, "nome": "Antigo", "email": "old@example.invalid", "senha_hash": "old-hash", "status": "Ativo"}
        conn = MagicMock(); conn.cursor.return_value = cursor
        context = MagicMock(); context.__enter__.return_value = conn
        pool = MagicMock(); pool.get_connection.return_value = context
        with patch.object(MasterUserManager, "_get_credentials", return_value=credentials), patch("db.master_user_manager.get_pool", return_value=pool), patch("db.master_user_manager.check_password", return_value=False), patch("db.master_user_manager.hash_password", return_value="new-hash"):
            self.assertTrue(MasterUserManager._create_master())
        self.assertTrue(any("UPDATE usuarios" in str(call.args[0]) for call in cursor.execute.call_args_list))

    def test_empty_database_requires_exact_existing_environment_variables(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(RuntimeError, "EMAIL_MASTER, SENHA_MASTER e USUARIO_MASTER"):
                MasterUserManager._create_master()

    def test_valid_environment_creates_exactly_one_master_without_logging_secrets(self):
        credentials = {"nome": "Master Sentinel", "email": "master-sentinel@example.invalid", "senha": "Secret-Sentinel-123", "telegram": None}
        cursor = MagicMock()
        cursor.fetchone.side_effect = [None, {"id": 42}]
        conn = MagicMock()
        conn.cursor.return_value = cursor
        connection_context = MagicMock()
        connection_context.__enter__.return_value = conn
        pool = MagicMock()
        pool.get_connection.return_value = connection_context

        with patch.object(MasterUserManager, "_master_exists", return_value=False), \
             patch.object(MasterUserManager, "_get_credentials", return_value=credentials), \
             patch("db.master_user_manager.get_pool", return_value=pool), \
             patch("db.master_user_manager.hash_password", return_value="bcrypt-hash"), \
             patch("db.master_user_manager.logger") as logger:
            self.assertTrue(MasterUserManager._create_master())

        inserts = [call for call in cursor.execute.call_args_list if "INSERT INTO usuarios" in str(call.args[0])]
        self.assertEqual(len(inserts), 1)
        self.assertNotIn(credentials["senha"], repr(cursor.execute.call_args_list))
        self.assertNotIn(credentials["nome"], repr(logger.method_calls))
        self.assertNotIn(credentials["email"], repr(logger.method_calls))

    def test_transactional_recheck_prevents_duplicate_master(self):
        cursor = MagicMock()
        cursor.fetchone.return_value = {"id": 1, "nome": "Master", "email": "master@example.invalid", "senha_hash": "existing-hash", "status": "Ativo"}
        conn = MagicMock()
        conn.cursor.return_value = cursor
        connection_context = MagicMock()
        connection_context.__enter__.return_value = conn
        pool = MagicMock()
        pool.get_connection.return_value = connection_context
        credentials = {"nome": "Master", "email": "master@example.invalid", "senha": "Secret-123", "telegram": None}

        with patch.object(MasterUserManager, "_master_exists", return_value=False), \
             patch.object(MasterUserManager, "_get_credentials", return_value=credentials), \
             patch("db.master_user_manager.get_pool", return_value=pool), \
             patch("db.master_user_manager.check_password", return_value=True), \
             patch("db.master_user_manager.hash_password") as hash_password:
            self.assertTrue(MasterUserManager._create_master())

        hash_password.assert_not_called()
        self.assertFalse(any("INSERT INTO usuarios" in str(call.args[0]) for call in cursor.execute.call_args_list))


if __name__ == "__main__":
    unittest.main()
