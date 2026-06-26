import unittest

import app


class AuthorizationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.original_chat_ids = set(app.ALLOWED_CHAT_IDS)
        self.original_user_ids = set(getattr(app, "ALLOWED_USER_IDS", set()))

    def tearDown(self) -> None:
        app.ALLOWED_CHAT_IDS = self.original_chat_ids
        app.ALLOWED_USER_IDS = self.original_user_ids

    def test_allows_configured_user_even_when_chat_id_is_different(self) -> None:
        app.ALLOWED_CHAT_IDS = set()
        app.ALLOWED_USER_IDS = {"111111111"}

        self.assertTrue(app.allowed_update(chat_id=-100123, user_id=111111111))

    def test_denies_allowed_chat_when_user_is_not_configured(self) -> None:
        app.ALLOWED_CHAT_IDS = {"-100123"}
        app.ALLOWED_USER_IDS = {"111111111"}

        self.assertFalse(app.allowed_update(chat_id=-100123, user_id=222222222))


if __name__ == "__main__":
    unittest.main()
