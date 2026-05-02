import unittest

from app import create_app


class AppSmokeTests(unittest.TestCase):
    def setUp(self):
        app = create_app()
        app.config['TESTING'] = True
        self.client = app.test_client()

    def test_root_page_is_available(self):
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)

    def test_login_with_valid_credentials(self):
        response = self.client.post('/api/auth/login',
            json={'username': 'admin', 'password': 'admin123'},
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertIn('token', data)

    def test_login_with_invalid_credentials(self):
        response = self.client.post('/api/auth/login',
            json={'username': 'admin', 'password': 'wrongpassword'},
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 401)

    def test_predict_requires_auth(self):
        response = self.client.post('/api/predict')
        self.assertEqual(response.status_code, 401)


if __name__ == '__main__':
    unittest.main()
