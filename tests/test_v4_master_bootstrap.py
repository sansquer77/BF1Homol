import os
import unittest
from unittest.mock import MagicMock, patch

from tests._db_driver_stub import install_if_needed

install_if_needed()

from db.master_user_manager import MasterUserManager


class MasterBootstrapV4Tests(unittest.TestCase):
    def test_existing_master_does_not_require_or_reset_environment_credentials(self):
        with patch.object(MasterUserManager, "_master_exists", return_value=True), \
             patch.object(MasterUserManager, "_get_credentials") as credentials:
            self.assertTrue(MasterUserManager._create_master())
        credentials.assert_not_called()

    def test_empty_database_requires_exact_existing_environment_variables(self):
        with patch.object(MasterUserManager, "_master_exists", return_value=False), \
             patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(RuntimeError, "EMAIL_MASTER, SENHA_MASTER e USUARIO_MASTER"):
                MasterUserManager._create_master()


if __name__ == "__main__":
    unittest.main()
