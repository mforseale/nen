import unittest
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

import test_workspace
from app.models import AuthSession, UserCredential
from app.routers.auth import COOKIE_NAME, _token_hash


class AuthTests(unittest.TestCase):
    def setUp(self):
        test_workspace.WorkspaceTests.setUp(self)

    def tearDown(self):
        test_workspace.WorkspaceTests.tearDown(self)

    def test_login_email_logout_and_revoked_token(self):
        self.assertEqual(self.a.post("/api/v1/auth/logout").status_code,204)
        self.assertEqual(self.a.get("/api/v1/auth/me").status_code,401)
        for login in ("alice","nobody"):
            response = self.a.post("/api/v1/auth/login",json={"login":login,"password":"wrong-password"})
            self.assertEqual(response.status_code,401,response.text)
        response = self.a.post("/api/v1/auth/login",json={"login":"ALICE@EXAMPLE.TEST","password":"test-password-123"})
        self.assertEqual(response.status_code,200,response.text)
        for attribute in ("HttpOnly","SameSite=lax","Path=/","Max-Age=2592000"):
            self.assertIn(attribute,response.headers["set-cookie"])
        token = self.a.cookies.get(COOKIE_NAME)
        user_id = response.json()["id"]
        with self.sessions() as db:
            credential = db.get(UserCredential,user_id)
            self.assertTrue(credential.password_hash.startswith("pbkdf2_sha256$"))
            self.assertNotIn("test-password-123",credential.password_hash)
            session = db.scalar(select(AuthSession).where(AuthSession.token_hash == _token_hash(token)))
            self.assertIsNotNone(session)
            self.assertNotEqual(session.token_hash,token)
        self.assertEqual(self.a.get("/api/v1/auth/me").json()["username"],"alice")
        self.assertEqual(self.a.post("/api/v1/auth/logout").status_code,204)
        self.assertEqual(self.anon.get("/api/v1/auth/me",headers={"Cookie":COOKIE_NAME+"="+token}).status_code,401)
        self.assertEqual(self.a.post("/api/v1/auth/logout").status_code,204)

    def test_expired_and_forged_sessions_cannot_access_private_data(self):
        self.assertEqual(self.anon.get("/api/v1/my/files",headers={"Cookie":COOKIE_NAME+"=forged"}).status_code,401)
        token = self.a.cookies.get(COOKIE_NAME)
        with self.sessions() as db:
            session = db.scalar(select(AuthSession).where(AuthSession.token_hash == _token_hash(token)))
            session.expires_at = datetime.now(timezone.utc)-timedelta(seconds=1)
            db.commit()
        for path in ("/api/v1/auth/me","/api/v1/my/profile","/api/v1/my/pacts","/api/v1/forum/posts?scope=mine"):
            self.assertEqual(self.a.get(path).status_code,401,path)
        with self.sessions() as db:
            self.assertIsNone(db.scalar(select(AuthSession).where(AuthSession.token_hash == _token_hash(token))))

    def test_registration_validation_and_normalized_duplicates(self):
        valid = {"username":"new_user","full_name":"New user","email":"new@example.test","password":"test-password-123"}
        for changed in ({"username":"bad/name"},{"full_name":"  "},{"email":"not-an-email"},{"password":"short"}):
            response = self.anon.post("/api/v1/auth/register",json={**valid,**changed})
            self.assertEqual(response.status_code,422,response.text)
        for changed in ({"username":" alice "},{"email":" ALICE@EXAMPLE.TEST "}):
            response = self.anon.post("/api/v1/auth/register",json={**valid,**changed})
            self.assertEqual(response.status_code,409,response.text)
        self.assertEqual(self.anon.get("/api/v1/auth/me").status_code,401)
