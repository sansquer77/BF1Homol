import unittest
from unittest.mock import MagicMock, patch

from services.access_control import AuthenticatedContext
from services.hall_admin_v4_service import list_hall_admin


class HallAdminV4Tests(unittest.TestCase):
    def test_listagem_aceita_cursor_dict_row_do_psycopg3(self):
        cursor = MagicMock()
        cursor.fetchall.side_effect = [
            [{
                "id": 4,
                "usuario_id": 7,
                "participante": "Participante",
                "temporada": "2026",
                "posicao_final": 1,
                "pontos": 321.5,
            }],
            [{"id": 7, "nome": "Participante"}],
        ]
        connection = MagicMock()
        connection.cursor.return_value = cursor
        manager = MagicMock()
        manager.__enter__.return_value = connection
        context = AuthenticatedContext(
            user_id=1,
            nome="Master",
            perfil="master",
            status="ativo",
            temporadas_autorizadas=frozenset(),
        )

        with patch("services.hall_admin_v4_service._master"), patch(
            "services.hall_admin_v4_service._db_connect", return_value=manager
        ):
            result = list_hall_admin(context, "2026")

        self.assertEqual(result["records"][0]["participant"], "Participante")
        self.assertEqual(result["records"][0]["points"], 321.5)
        self.assertEqual(result["participants"], [{"id": 7, "name": "Participante"}])


if __name__ == "__main__":
    unittest.main()
