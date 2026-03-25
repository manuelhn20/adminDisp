import unittest
from unittest.mock import MagicMock

from admin_disp.devices.service import DeviceService


class DeviceServiceOrmMigrationTests(unittest.TestCase):
    def _service_with_engine(self):
        svc = DeviceService.__new__(DeviceService)
        svc.engine = MagicMock()
        svc.has_column = MagicMock(return_value=False)
        return svc

    def test_create_componente_works_with_engine_only(self):
        svc = self._service_with_engine()
        conn = MagicMock()
        svc.engine.begin.return_value.__enter__.return_value = conn

        insert_result = MagicMock()
        insert_result.first.return_value = (123,)
        conn.execute.return_value = insert_result

        new_id = svc.create_componente(
            fk_id_dispositivo=7,
            tipo_componente="RAM",
            capacidad=8,
            tipo_memoria="DDR4",
        )

        self.assertEqual(new_id, 123)

    def test_update_componente_works_with_engine_only(self):
        svc = self._service_with_engine()
        conn = MagicMock()
        svc.engine.begin.return_value.__enter__.return_value = conn
        conn.execute.return_value = MagicMock(rowcount=1)

        ok = svc.update_componente(5, observaciones="actualizado")

        self.assertTrue(ok)

    def test_delete_componente_works_with_engine_only(self):
        svc = self._service_with_engine()
        conn = MagicMock()
        svc.engine.begin.return_value.__enter__.return_value = conn
        conn.execute.return_value = MagicMock(rowcount=1)

        ok = svc.delete_componente(9)

        self.assertTrue(ok)

    def test_create_marca_works_with_engine_only(self):
        svc = self._service_with_engine()
        conn = MagicMock()
        svc.engine.begin.return_value.__enter__.return_value = conn

        no_duplicate = MagicMock()
        no_duplicate.first.return_value = None
        inserted = MagicMock()
        inserted.first.return_value = (55,)
        conn.execute.side_effect = [no_duplicate, inserted]

        marca_id, nombre = svc.create_marca(" Lenovo ")

        self.assertEqual(marca_id, 55)
        self.assertEqual(nombre, "Lenovo")

    def test_create_modelo_works_with_engine_only(self):
        svc = self._service_with_engine()
        conn = MagicMock()
        svc.engine.begin.return_value.__enter__.return_value = conn

        no_duplicate = MagicMock()
        no_duplicate.first.return_value = None
        inserted = MagicMock()
        inserted.first.return_value = (77,)
        conn.execute.side_effect = [no_duplicate, inserted]

        modelo_id = svc.create_modelo("EliteBook", "Laptop", 4, estado=1, salidas=2, capacidad="512GB")

        self.assertEqual(modelo_id, 77)

    def test_set_modelo_estado_works_with_engine_only(self):
        svc = self._service_with_engine()
        conn = MagicMock()
        svc.engine.begin.return_value.__enter__.return_value = conn
        conn.execute.return_value = MagicMock(rowcount=1)

        result = svc.set_modelo_estado(7, 1)

        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
