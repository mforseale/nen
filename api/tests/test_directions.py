import unittest
from datetime import datetime, timezone

import test_workspace
from app.directions import CATEGORIES, TIERS
from app.models import Pact, PactCheckin, PactDetails, PactParticipant, PactRarity, PactStatus, PactTopic


class DirectionTests(unittest.TestCase):
    def setUp(self):
        test_workspace.WorkspaceTests.setUp(self)

    def tearDown(self):
        test_workspace.WorkspaceTests.tearDown(self)

    def create(self, category="Тело", rarity="common", client=None, title=None):
        return (client or self.a).post("/api/v1/my/pacts", json={"title": title or f"{category} {rarity}", "description": "Practice twenty minutes every day", "category": category, "rarity": rarity})

    def fill(self, category="Тело", rarity="common", client=None):
        for index in range(3):
            response = self.create(category, rarity, client, f"{category} {rarity} {index}")
            self.assertEqual(response.status_code, 201, response.text)

    def invitation(self):
        response = self.a.post("/api/v1/requests", json={"recipient":"boris","title":"Together daily","description":"Twenty minutes every day","duration_days":7,"category":"Социум"})
        self.assertEqual(response.status_code, 201, response.text)
        item = self.b.get("/api/v1/requests").json()[0]
        self.assertEqual(item["category"], "Социум")
        self.assertEqual(item["rarity"], "common")
        return item

    def test_unlimited_per_tier_per_direction_and_independent_cells(self):
        for category in CATEGORIES:
            for tier in TIERS:
                self.fill(category, tier)
                response = self.create(category, tier, title=f"Overflow {category} {tier}")
                self.assertEqual(response.status_code, 201, response.text)
        capacity = self.a.get("/api/v1/my/pacts/capacity").json()
        self.assertIsNone(capacity["limit"])
        self.assertEqual(set(capacity["counts"]), set(CATEGORIES))
        self.assertTrue(all(count == 4 for tiers in capacity["counts"].values() for count in tiers.values()))
        self.assertEqual(len(self.a.get("/api/v1/my/pacts").json()), 96)
        self.assertEqual(self.b.get("/api/v1/my/pacts").json(), [])
        self.assertEqual(self.anon.get("/api/v1/my/pacts/capacity").status_code, 401)

    def test_personal_pacts_can_move_into_populated_direction_and_keep_history(self):
        self.fill("Разум")
        self.assertEqual(self.create(category="\u0420\u0430\u0437\u0443\u043c", title="Read pages").status_code, 201)
        walk = self.create(title="Daily walk")
        self.assertEqual(walk.status_code, 201, walk.text)
        self.assertEqual(walk.json()["category"], "Тело")
        self.assertEqual(self.a.put(f"/api/v1/my/pacts/{walk.json()['id']}/category", json={"category":"Разум"}).status_code, 200)
        mind = next(p for p in self.a.get("/api/v1/my/pacts").json() if p["category"] == "Разум")
        day = datetime.now(timezone.utc).date().isoformat()
        self.a.post(f"/api/v1/my/pacts/{mind['id']}/checkin", json={"day":day})
        result = self.a.post(f"/api/v1/my/pacts/{mind['id']}/cancel")
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.json()["checkins"], [day])
        self.assertEqual(result.json()["status"], "cancelled")
        self.assertEqual(self.create(category="\u0420\u0430\u0437\u0443\u043c", title="Another read pact").status_code, 201)

    def test_joint_acceptance_with_many_pacts_is_allowed_for_both_members(self):
        item = self.invitation()
        self.fill("Социум", client=self.b)
        self.fill("Социум")
        response = self.b.post(f"/api/v1/requests/{item['id']}/respond", json={"accept":True})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(self.b.get("/api/v1/requests").json()[0]["status"], "accepted")
        for client in (self.a,self.b):
            self.assertEqual(client.get("/api/v1/my/pacts/capacity").json()["counts"]["Социум"]["common"], 4)

    def test_decline_is_allowed_when_full_and_drafts_do_not_reserve_capacity(self):
        item = self.invitation()
        self.assertEqual(self.a.get("/api/v1/my/pacts/capacity").json()["counts"]["Социум"]["common"], 0)
        self.fill("Социум", client=self.b)
        self.assertEqual(self.b.post(f"/api/v1/requests/{item['id']}/respond", json={"accept":False}).status_code, 200)
        self.assertEqual(self.a.get("/api/v1/my/pacts/capacity").json()["counts"]["Социум"]["common"], 0)

    def test_joint_move_checks_both_participants_and_non_author_cannot_manage(self):
        item = self.invitation()
        self.b.post(f"/api/v1/requests/{item['id']}/respond", json={"accept":True})
        pid = item["pact_id"]
        self.fill("Тело", client=self.b)
        self.assertEqual(self.a.put(f"/api/v1/my/pacts/{pid}/category", json={"category":"Тело"}).status_code, 200)
        self.assertEqual(self.b.put(f"/api/v1/my/pacts/{pid}/category", json={"category":"Разум"}).status_code, 403)
        self.assertEqual(self.b.post(f"/api/v1/my/pacts/{pid}/cancel").status_code, 403)
        moved = self.a.put(f"/api/v1/my/pacts/{pid}/category", json={"category":"Разум"})
        self.assertEqual(moved.status_code, 200, moved.text)
        self.assertEqual(moved.json()["category"], "Разум")
        self.assertEqual(self.b.get("/api/v1/my/pacts/capacity").json()["counts"]["Разум"]["common"], 1)
        self.assertEqual(self.a.post(f"/api/v1/my/pacts/{pid}/cancel").status_code, 200)
        self.assertEqual(self.b.get("/api/v1/my/pacts/capacity").json()["counts"]["Разум"]["common"], 0)

    def test_legacy_topics_and_over_capacity_are_projected_without_data_loss(self):
        uid = self.a.get("/api/v1/auth/me").json()["id"]
        with self.sessions() as db:
            for index in range(4):
                pact = Pact(title=f"Legacy {index}", description="Original terms", creator_id=uid, rarity=PactRarity.common, status=PactStatus.active)
                db.add(pact);db.flush()
                db.add_all([PactDetails(pact_id=pact.id, duration_days=7), PactTopic(pact_id=pact.id, category="Здоровье"), PactParticipant(pact_id=pact.id, user_id=uid), PactCheckin(pact_id=pact.id,user_id=uid,day=datetime.now(timezone.utc).date())])
            db.commit()
        pacts = self.a.get("/api/v1/my/pacts").json()
        self.assertEqual(len(pacts),4)
        self.assertTrue(all(p["category"] == "Тело" and p["description"] == "Original terms" and len(p["checkins"]) == 1 for p in pacts))
        self.assertEqual(self.a.get("/api/v1/my/pacts/capacity").json()["counts"]["Тело"]["common"],4)
        self.assertEqual(self.create(title="Fifth now allowed").status_code,201)
        pid = pacts[0]["id"]
        moved = self.a.put(f"/api/v1/my/pacts/{pid}/category",json={"category":"Другое"})
        self.assertEqual(moved.status_code,200,moved.text)
        self.assertEqual(moved.json()["checkins"],pacts[0]["checkins"])
        self.assertEqual(moved.json()["created_at"],pacts[0]["created_at"])
        self.assertEqual(len(self.a.get("/api/v1/my/pacts").json()),5)

    def test_unknown_direction_input_is_rejected(self):
        self.assertEqual(self.create("invented").status_code,422)
        self.assertEqual(self.create("Развитие").status_code,422)
