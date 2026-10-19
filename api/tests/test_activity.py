import json
import unittest

from fastapi.testclient import TestClient

import test_workspace
from app.main import app


class ActivityTests(unittest.TestCase):
    def setUp(self):
        test_workspace.WorkspaceTests.setUp(self)

    def tearDown(self):
        test_workspace.WorkspaceTests.tearDown(self)

    def post(self, client, title, visibility):
        response = client.post("/api/v1/my/feed", data={"payload":json.dumps({"title":title,"content":"Activity content","visibility":visibility})})
        self.assertEqual(response.status_code,201,response.text)
        return response.json()["id"]

    def ids(self, client, scope):
        response = client.get("/api/v1/forum/posts?scope="+scope)
        self.assertEqual(response.status_code,200,response.text)
        return {post["id"] for post in response.json()}

    def test_post_scopes_intersect_visibility_and_accepted_authors(self):
        own = {audience:self.post(self.a,"Alice "+audience,audience) for audience in ("public","friends","private")}
        boris = {audience:self.post(self.b,"Boris "+audience,audience) for audience in ("public","friends","private")}
        with TestClient(app) as third:
            response = third.post("/api/v1/auth/register",json={"username":"charlie","full_name":"Charlie","email":"charlie@example.test","password":"test-password-123"})
            self.assertEqual(response.status_code,201,response.text)
            outsider = self.post(third,"Charlie public","public")
            self.post(third,"Charlie private","private")
        self.assertEqual(self.ids(self.a,"mine"),set(own.values()))
        self.assertEqual(self.ids(self.a,"friends"),set())
        fid = self.a.post("/api/v1/friends",json={"username":"boris"}).json()["id"]
        self.assertEqual(self.ids(self.a,"friends"),set())
        self.b.post(f"/api/v1/friends/{fid}/respond",json={"accept":True})
        self.assertEqual(self.ids(self.a,"friends"),{boris["public"],boris["friends"]})
        self.assertEqual(self.ids(self.a,"all"),set(own.values())|{boris["public"],boris["friends"],outsider})
        self.assertEqual(self.ids(self.anon,"all"),{own["public"],boris["public"],outsider})
        self.assertEqual(self.ids(self.b,"friends"),{own["public"],own["friends"]})
        self.a.delete(f"/api/v1/friends/{fid}")
        self.assertEqual(self.ids(self.a,"friends"),set())
        self.assertNotIn(boris["friends"],self.ids(self.a,"all"))

    def test_guest_personal_scopes_require_login_and_unknown_scopes_are_rejected(self):
        for endpoint in ("/api/v1/forum/posts","/api/v1/forum"):
            for scope in ("friends","mine"):
                response = self.anon.get(endpoint+"?scope="+scope)
                self.assertEqual(response.status_code,401,response.text)
            self.assertEqual(self.a.get(endpoint+"?scope=invalid").status_code,422)

    def test_discussion_scopes_and_trending_keep_membership_restrictions(self):
        self.a.post("/api/v1/requests",json={"recipient":"boris","title":"Shared practice","description":"Practice together daily","duration_days":7})
        invitation = self.b.get("/api/v1/requests").json()[0]
        self.b.post(f"/api/v1/requests/{invitation['id']}/respond",json={"accept":True})
        pid = invitation["pact_id"]
        for client, content in ((self.a,"Alice shared"),(self.b,"Boris shared")):
            response = client.post("/api/v1/forum",json={"pact_id":pid,"content":content})
            self.assertEqual(response.status_code,201,response.text)
        private = self.b.post("/api/v1/my/pacts",json={"title":"Boris secret","description":"Private daily commitment"}).json()["id"]
        self.b.post("/api/v1/forum",json={"pact_id":private,"content":"Hidden even from friends"})
        self.assertEqual(self.a.get("/api/v1/forum?scope=friends").json()["comments"],[])
        fid = self.a.post("/api/v1/friends",json={"username":"boris"}).json()["id"]
        self.b.post(f"/api/v1/friends/{fid}/respond",json={"accept":True})
        for scope, contents, count in (("all",{"Alice shared","Boris shared"},2),("friends",{"Boris shared"},1),("mine",{"Alice shared"},1)):
            data = self.a.get("/api/v1/forum?scope="+scope).json()
            self.assertEqual({comment["content"] for comment in data["comments"]},contents)
            self.assertEqual(data["trending"][0]["count"],count)
            self.assertEqual(data["trending"][0]["pact_id"],pid)
        self.assertEqual(self.a.get(f"/api/v1/forum?pact_id={private}&scope=friends").status_code,404)
        self.assertEqual(self.anon.get("/api/v1/forum").json()["comments"],[])
