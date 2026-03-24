import unittest

from admin_disp.services.docexp import select_template


class TemplateSelectionTests(unittest.TestCase):
    def test_select_template_returns_existing_file_for_supported_categories(self):
        categories = ["Celular", "Laptop", "Tablet", "Mouse"]

        for category in categories:
            with self.subTest(category=category):
                template_path = select_template(category)
                self.assertTrue(
                    template_path.exists(),
                    f"Template no existe para categoria {category}: {template_path}",
                )


if __name__ == "__main__":
    unittest.main()
