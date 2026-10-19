import base64
import unittest
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

import test_workspace
from app.models import Pact, PactCheckin, PactStatus, User

PNG = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/l9sAAAAASUVORK5CYII="


class CommunityTests(unittest.TestCase):
    def setUp(self):
        test_workspace.WorkspaceTests.setUp(self)

    def tearDown(self):
        test_workspace.WorkspaceTests.tearDown(self)

    def pact(self, **overrides):
        data = {"title": "My own pact", "description": "Twenty minutes of practice every day", "rarity": "common", "category": "Разум", **overrides}
        response = self.a.post("/api/v1/my/pacts", json=data)
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()

    def friend(self):
        response = self.a.post("/api/v1/friends", json={"username": "@boris"})
        self.assertEqual(response.status_code, 201, response.text)
        fid = response.json()["id"]
        response = self.b.post(f"/api/v1/friends/{fid}/respond", json={"accept": True})
        self.assertEqual(response.status_code, 200, response.text)
        return fid

    def test_custom_pacts_have_real_tiers_categories_and_private_access(self):
        self.assertEqual(self.anon.post("/api/v1/my/pacts", json={}).status_code, 401)
        for rarity, days in [("common", 7), ("rare", None), ("epic", None), ("legendary", None)]:
            item = self.pact(title="My pact " + rarity, rarity=rarity)
            self.assertTrue(item["is_custom"])
            self.assertEqual(item["status"], "active")
            self.assertEqual(item["category"], "Разум")
            self.assertEqual(item["rarity"], rarity)
            if days:
                self.assertEqual(item["duration_days"], days)
            if rarity == "rare":
                self.assertIn(item["duration_days"], (28, 29, 30, 31))
            if rarity == "epic":
                self.assertIn(item["duration_days"], (365, 366))
            if rarity == "legendary":
                self.assertIsNone(item["deadline"])
                self.assertIsNone(item["progress"])
            day = datetime.now(timezone.utc).date().isoformat()
            self.assertEqual(self.b.post(f"/api/v1/my/pacts/{item['id']}/checkin", json={"day": day}).status_code, 404)
        self.assertEqual(self.b.get("/api/v1/my/pacts").json(), [])
        self.assertEqual(self.anon.get("/api/v1/people/alice").json()["notes"], [])
        self.assertNotIn("My pact", self.anon.get("/api/v1/search?kind=pacts&q=My").text)
        self.assertEqual(self.a.post("/api/v1/my/pacts", json={"title": "   ", "description": "ten characters", "category": "Разум"}).status_code, 422)
        self.assertEqual(self.a.post("/api/v1/my/pacts", json={"title": "Invalid", "description": "ten characters", "category": "invented"}).status_code, 422)

    def test_checkin_all_is_idempotent_and_scoped_to_active_member(self):
        one, two, expired = [self.pact(title=name) for name in ["First pact", "Second pact", "Expired pact"]]
        other = self.b.post("/api/v1/my/pacts", json={"title":"Morning practice", "description":"Practice every morning", "rarity":"common"}).json()
        day = datetime.now(timezone.utc).date().isoformat()
        with self.sessions() as db:
            db.get(Pact, expired["id"]).deadline = datetime.now(timezone.utc) - timedelta(seconds=1)
            db.commit()
        self.a.post(f"/api/v1/my/pacts/{one['id']}/checkin", json={"day": day})
        result = self.a.post("/api/v1/my/pacts/checkin-all", json={"day": day})
        self.assertEqual(result.status_code, 200, result.text)
        self.assertEqual(result.json()["marked"], [two["id"]])
        self.assertEqual(result.json()["already_marked"], [one["id"]])
        self.assertEqual(result.json()["expired"], [expired["id"]])
        again = self.a.post("/api/v1/my/pacts/checkin-all", json={"day": day}).json()
        self.assertEqual(again["marked"], [])
        self.assertEqual(len(again["already_marked"]), 2)
        self.assertEqual(self.b.get("/api/v1/my/pacts").json()[0]["checkins"], [])
        future = (datetime.now(timezone.utc) + timedelta(days=2)).date().isoformat()
        self.assertEqual(self.a.post("/api/v1/my/pacts/checkin-all", json={"day": future}).status_code, 422)
        self.assertEqual(self.anon.post("/api/v1/my/pacts/checkin-all", json={"day": day}).status_code, 401)
        with self.sessions() as db:
            self.assertEqual(len(db.scalars(select(PactCheckin)).all()), 2)
            self.assertNotIn(other["id"], result.json()["marked"])

    def test_batch_only_marks_current_participant_of_joint_pact(self):
        self.a.post("/api/v1/requests", json={"recipient": "boris", "title": "Joint task", "description": "Twenty minutes every day", "duration_days": 3})
        rid = self.b.get("/api/v1/requests").json()[0]["id"]
        self.b.post(f"/api/v1/requests/{rid}/respond", json={"accept": True})
        day = datetime.now(timezone.utc).date().isoformat()
        result = self.a.post("/api/v1/my/pacts/checkin-all", json={"day": day}).json()
        self.assertEqual(len(result["marked"]), 1)
        self.assertEqual(self.b.get("/api/v1/my/pacts").json()[0]["checkins"], [])

    def test_bulk_skips_completed_draft_and_capped_pacts_with_local_day(self):
        capped = self.pact(title="Capped pact")
        historical = self.pact(title="Historical pact")
        available = self.pact(title="Available pact")
        self.a.post("/api/v1/requests", json={"recipient": "boris", "title": "Pending task", "description": "Twenty minutes every day", "duration_days": 7})
        now = datetime.now(timezone.utc)
        day = (now + timedelta(hours=7)).date()
        with self.sessions() as db:
            alice = db.scalar(select(User).where(User.username == "alice"))
            db.get(Pact, historical["id"]).status = PactStatus.completed
            for offset in range(1, 8):
                db.add(PactCheckin(pact_id=capped["id"], user_id=alice.id, day=day - timedelta(days=offset)))
            db.commit()
        response = self.a.post("/api/v1/my/pacts/checkin-all", json={"day": day.isoformat(), "utc_offset_minutes": 420})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["marked"], [available["id"]])
        self.assertEqual(response.json()["at_limit"], [capped["id"]])
        items = self.a.get("/api/v1/my/pacts").json()
        self.assertEqual(next(p for p in items if p["status"] == "draft")["checkins"], [])
        self.assertEqual(next(p for p in items if p["id"] == historical["id"])["checkins"], [])

    def test_custom_duplicate_names_are_normalized_for_cyrillic(self):
        self.pact(title="Мой ежедневный пакт")
        response = self.a.post("/api/v1/my/pacts", json={"title": "  МОЙ ЕЖЕДНЕВНЫЙ ПАКТ  ", "description": "Twenty minutes every day", "rarity": "epic"})
        self.assertEqual(response.status_code, 409, response.text)
        self.assertEqual(len(self.a.get("/api/v1/my/pacts").json()), 1)

    def test_friendship_requires_recipient_and_no_duplicate_pair(self):
        item = self.a.post("/api/v1/friends", json={"username": "boris"}).json()
        fid = item["id"]
        self.assertEqual(self.a.post("/api/v1/friends", json={"username": "alice"}).status_code, 422)
        self.assertEqual(self.a.post("/api/v1/friends", json={"username": "missing"}).status_code, 404)
        self.assertEqual(self.b.post("/api/v1/friends", json={"username": "alice"}).status_code, 409)
        self.assertEqual(self.a.post(f"/api/v1/friends/{fid}/respond", json={"accept": True}).status_code, 403)
        self.assertEqual(self.anon.get("/api/v1/friends").status_code, 401)
        self.assertEqual(self.b.get("/api/v1/people/alice").json()["friendship"]["status"], "incoming")
        self.assertEqual(self.a.get("/api/v1/people/boris").json()["friendship"]["status"], "outgoing")
        self.assertEqual(self.b.post(f"/api/v1/friends/{fid}/respond", json={"accept": True}).status_code, 200)
        self.assertEqual(self.b.post(f"/api/v1/friends/{fid}/respond", json={"accept": True}).status_code, 409)
        self.assertEqual(self.a.get("/api/v1/my/profile").json()["friend_count"], 1)
        self.assertEqual(self.a.get("/api/v1/friends").json()[0]["status"], "accepted")
        self.assertEqual(self.b.delete(f"/api/v1/friends/{fid}").status_code, 204)
        self.assertEqual(self.a.get("/api/v1/my/profile").json()["friend_count"], 0)

    def test_friend_decline_cancel_and_retry(self):
        fid = self.a.post("/api/v1/friends", json={"username": "boris"}).json()["id"]
        self.assertEqual(self.b.delete(f"/api/v1/friends/{fid}").status_code, 403)
        self.assertEqual(self.b.post(f"/api/v1/friends/{fid}/respond", json={"accept": False}).status_code, 200)
        retry = self.b.post("/api/v1/friends", json={"username": "alice"})
        self.assertEqual(retry.status_code, 201, retry.text)
        self.assertEqual(retry.json()["id"], fid)
        self.assertEqual(self.b.delete(f"/api/v1/friends/{fid}").status_code, 204)
        self.assertEqual(self.a.get("/api/v1/friends").json(), [])

    def test_year_goals_ownership_visibility_and_progress_validation(self):
        ids = {}
        for audience in ["private", "friends", "public"]:
            response = self.a.post("/api/v1/my/goals", json={"year": 2026, "title": audience, "target": 12, "current": 3, "unit": "книг", "visibility": audience})
            self.assertEqual(response.status_code, 201, response.text)
            ids[audience] = response.json()["id"]
        self.assertEqual(len(self.anon.get("/api/v1/people/alice").json()["goals"]), 1)
        self.assertEqual(len(self.b.get("/api/v1/people/alice").json()["goals"]), 1)
        fid = self.friend()
        self.assertEqual(len(self.b.get("/api/v1/people/alice").json()["goals"]), 2)
        self.assertEqual(len(self.a.get("/api/v1/my/profile").json()["goals"]), 3)
        payload = {"year": 2027, "title": "Read books", "target": 12, "current": 12}
        self.assertEqual(self.b.put(f"/api/v1/my/goals/{ids['private']}", json=payload).status_code, 404)
        self.assertEqual(self.b.delete(f"/api/v1/my/goals/{ids['private']}").status_code, 404)
        updated = self.a.put(f"/api/v1/my/goals/{ids['private']}", json=payload)
        self.assertEqual(updated.status_code, 200, updated.text)
        self.assertEqual(updated.json()["current"], 12)
        self.assertEqual(self.a.post("/api/v1/my/goals", json={**payload, "current": 13}).status_code, 422)
        self.assertEqual(self.a.post("/api/v1/my/goals", json={**payload, "target": 0}).status_code, 422)
        self.b.delete(f"/api/v1/friends/{fid}")
        self.assertEqual(len(self.b.get("/api/v1/people/alice").json()["goals"]), 1)
        self.assertEqual(self.a.delete(f"/api/v1/my/goals/{ids['private']}").status_code, 204)

    def test_profile_settings_avatar_and_public_projection(self):
        response = self.a.put("/api/v1/my/profile", json={"full_name": "Alice Updated", "bio": "About me", "accent": "gold"})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(self.a.get("/api/v1/auth/me").json()["full_name"], "Alice Updated")
        public = self.anon.get("/api/v1/people/alice").json()
        self.assertEqual(public["bio"], "About me")
        self.assertEqual(public["accent"], "gold")
        self.assertNotIn("email", public["user"])
        response = self.a.put("/api/v1/my/profile/avatar", json={"data_url": PNG})
        self.assertEqual(response.status_code, 200, response.text)
        image = self.anon.get(response.json()["avatar_url"])
        self.assertEqual(image.status_code, 200)
        self.assertEqual(image.headers["content-type"], "image/png")
        self.assertEqual(image.headers["x-content-type-options"], "nosniff")
        self.assertEqual(image.content, base64.b64decode(PNG.split(",")[1]))
        for invalid in ["data:image/svg+xml;base64,PHN2Zy8+", "data:image/png;base64,ZmFrZQ=="]:
            self.assertEqual(self.a.put("/api/v1/my/profile/avatar", json={"data_url": invalid}).status_code, 422)
        self.assertEqual(self.a.delete("/api/v1/my/profile/avatar").status_code, 204)
        self.assertIsNone(self.a.get("/api/v1/my/profile").json()["user"]["avatar_url"])
        self.assertEqual(self.anon.get("/api/v1/people/alice/avatar").status_code, 404)

    def test_one_addressable_profile_returns_private_content_only_to_its_owner(self):
        self.a.post("/api/v1/my/posts",json={"title":"Personal post","content":"Owner only","visibility":"private"})
        self.a.post("/api/v1/notes",json={"title":"Personal note","content":"Owner only","visibility":"private"})
        self.a.post("/api/v1/my/goals",json={"title":"Personal goal","year":2026,"target":12,"current":1,"unit":"books","visibility":"private"})
        response = self.a.get("/api/v1/people/alice")
        self.assertEqual(response.status_code,200,response.text)
        self.assertEqual(response.headers["cache-control"],"private, no-store")
        own = response.json()
        self.assertEqual(own["friendship"]["status"],"self")
        for collection in ("posts","notes","goals"):
            self.assertEqual(len(own[collection]),1,collection)
        for viewer in (self.b,self.anon):
            data = viewer.get("/api/v1/people/alice").json()
            for collection in ("posts","notes","goals"):
                self.assertEqual(data[collection],[],collection)
            self.assertNotIn("email",data["user"])

    def test_post_types_images_audience_and_revocation(self):
        posts = {}
        for audience in ["private", "friends", "public"]:
            response = self.a.post("/api/v1/my/posts", json={"kind": "image", "title": audience, "image_data": PNG, "visibility": audience})
            self.assertEqual(response.status_code, 201, response.text)
            posts[audience] = response.json()
        self.assertEqual(self.anon.get(posts["private"]["image_url"]).status_code, 404)
        self.assertEqual(self.b.get(posts["friends"]["image_url"]).status_code, 404)
        self.assertEqual(self.anon.get(posts["public"]["image_url"]).status_code, 200)
        fid = self.friend()
        self.assertEqual(self.b.get(posts["friends"]["image_url"]).status_code, 200)
        self.assertEqual(len(self.b.get("/api/v1/people/alice").json()["posts"]), 2)
        pid = posts["private"]["id"]
        payload = {"kind": "music", "title": "My song", "url": "https://example.org/song", "content": "Why it matters"}
        self.assertEqual(self.b.put(f"/api/v1/my/posts/{pid}", json=payload).status_code, 404)
        self.assertEqual(self.b.delete(f"/api/v1/my/posts/{pid}").status_code, 404)
        changed = self.a.put(f"/api/v1/my/posts/{pid}", json={**payload, "remove_image": True})
        self.assertEqual(changed.status_code, 200, changed.text)
        self.assertIsNone(changed.json()["image_url"])
        self.b.delete(f"/api/v1/friends/{fid}")
        self.assertEqual(self.b.get(posts["friends"]["image_url"]).status_code, 404)
        self.assertEqual(len(self.b.get("/api/v1/people/alice").json()["posts"]), 1)
        public = posts["public"]
        response = self.a.put(f"/api/v1/my/posts/{public['id']}", json={"kind": "image", "title": "Now private", "visibility": "private"})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(self.anon.get(public["image_url"]).status_code, 404)
        self.assertEqual(self.a.delete(f"/api/v1/my/posts/{pid}").status_code, 204)

    def test_post_content_urls_and_image_validation(self):
        for url in ["javascript:alert(1)", "data:text/html,test", "https://user:pass@example.org", "https://example.org/a\nb"]:
            response = self.a.post("/api/v1/my/posts", json={"kind": "link", "title": "Bad link", "url": url})
            self.assertEqual(response.status_code, 422, response.text)
        for payload in [{"kind": "image", "title": "Missing image"}, {"kind": "post", "title": "Empty text"}, {"kind": "link", "title": "Missing URL"}]:
            self.assertEqual(self.a.post("/api/v1/my/posts", json=payload).status_code, 422)
        for kind in ["music", "film", "book", "link", "post"]:
            result = self.a.post("/api/v1/my/posts", json={"kind": kind, "title": "Inspiration", "content": "A personal recommendation", "url": "https://example.org/item"})
            self.assertEqual(result.status_code, 201, result.text)

    def test_achievements_use_own_real_checkins_and_tier_topic(self):
        pacts = []
        for index in range(6):
            if index >= 3:
                with self.sessions() as db:
                    db.get(Pact, pacts[index - 3]["id"]).status = PactStatus.completed
                    db.commit()
            pacts.append(self.pact(title=f"Practice {index}"))
        before = self.a.get("/api/v1/my/profile").json()["achievements"]
        self.assertFalse(any(item["earned"] for item in before))
        day = datetime.now(timezone.utc).date()
        with self.sessions() as db:
            alice = db.scalar(select(User).where(User.username == "alice"))
            boris = db.scalar(select(User).where(User.username == "boris"))
            alice_id = alice.id
            for pact in pacts[:5]:
                db.add(PactCheckin(pact_id=pact["id"], user_id=alice.id, day=day))
            # Someone else's mark must not award the owner anything extra.
            db.add(PactCheckin(pact_id=pacts[5]["id"], user_id=boris.id, day=day))
            db.commit()
        earned = {item["id"]: item for item in self.a.get("/api/v1/my/profile").json()["achievements"]}
        self.assertTrue(earned["first-step"]["earned"])
        self.assertTrue(earned["tier-common"]["earned"])
        self.assertEqual(earned["tier-common"]["count"], 5)
        topic = next(item for item in earned.values() if item["title"] == "Разум")
        self.assertTrue(topic["earned"])
        self.assertFalse(earned["tier-epic"]["earned"])
        self.assertFalse(earned["kept-word"]["earned"])
        self.assertEqual(self.anon.get("/api/v1/people/alice").json()["achievements"], list(earned.values()))
        with self.sessions() as db:
            pact = db.get(Pact, pacts[0]["id"])
            pact.status = PactStatus.completed
            for offset in range(1, 6):
                db.add(PactCheckin(pact_id=pact.id, user_id=alice_id, day=day - timedelta(days=offset)))
            db.commit()
        final = {item["id"]: item for item in self.a.get("/api/v1/my/profile").json()["achievements"]}
        self.assertTrue(final["kept-word"]["earned"])
        self.assertEqual(final["tier-common"]["count"], 5)
