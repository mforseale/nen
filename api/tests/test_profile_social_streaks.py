import json
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from sqlalchemy import func, select

import test_workspace
from app.models import (Pact, PactBreak, PactCheckin, PactDetails, PactStatus,
                        PactTracking, ProfilePostComment, ProfilePostLike, User)
from app.streaks import tracking_view
from test_feed import AUDIO


class ProfileSocialStreakTests(unittest.TestCase):
    def setUp(self):
        test_workspace.WorkspaceTests.setUp(self)

    def tearDown(self):
        test_workspace.WorkspaceTests.tearDown(self)

    def post(self, visibility="public"):
        response = self.a.post("/api/v1/my/feed", data={"payload": json.dumps({"content":"A conversation", "visibility":visibility})})
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()

    def pact(self, rarity="legendary"):
        response = self.a.post("/api/v1/my/pacts", json={"title":"A lasting promise", "description":"Practice every day", "rarity":rarity, "utc_offset_minutes":420})
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()

    def friend(self):
        fid = self.a.post("/api/v1/friends", json={"username":"boris"}).json()["id"]
        self.assertEqual(self.b.post(f"/api/v1/friends/{fid}/respond", json={"accept":True}).status_code, 200)
        return fid

    def test_likes_are_idempotent_and_projected_for_each_viewer(self):
        post = self.post()
        url = f"/api/v1/profile/posts/{post['id']}"
        self.assertEqual(post["likes_count"], 0)
        self.assertFalse(post["liked_by_me"])
        for _ in range(2):
            response = self.b.put(url+"/like")
            self.assertEqual(response.status_code, 200, response.text)
            self.assertEqual(response.json()["likes_count"], 1)
            self.assertTrue(response.json()["liked_by_me"])
        self.assertFalse(self.a.get(url).json()["liked_by_me"])
        self.assertTrue(self.b.get("/api/v1/forum/posts").json()[0]["liked_by_me"])
        self.assertFalse(self.anon.get("/api/v1/people/alice").json()["posts"][0]["liked_by_me"])
        self.assertEqual(self.anon.put(url+"/like").status_code, 401)
        for _ in range(2):
            self.assertEqual(self.b.delete(url+"/like").json()["likes_count"], 0)

    def test_comments_validate_and_allow_author_or_post_owner_to_remove(self):
        post = self.post()
        url = f"/api/v1/profile/posts/{post['id']}/comments"
        self.assertEqual(self.anon.post(url, json={"content":"No session"}).status_code, 401)
        for content in (" ", "x"*3001):
            self.assertEqual(self.b.post(url, json={"content":content}).status_code, 422)
        comment = self.b.post(url, json={"content":" **Keep going** "}).json()
        self.assertEqual(comment["content"], "**Keep going**")
        self.assertEqual(comment["author"]["username"], "boris")
        self.assertNotIn("email", comment["author"])
        self.assertTrue(comment["can_delete"])
        self.assertFalse(self.anon.get(url).json()[0]["can_delete"])
        self.assertTrue(self.a.get(url).json()[0]["can_delete"])
        self.assertEqual(self.a.get(f"/api/v1/profile/posts/{post['id']}").json()["comments_count"], 1)
        self.assertEqual(self.a.delete(url+f"/{comment['id']}").status_code, 204)
        self.assertEqual(self.b.get(url).json(), [])
        own = self.b.post(url, json={"content":"Another one"}).json()
        self.assertEqual(self.b.delete(url+f"/{own['id']}").status_code, 204)
        owner_comment = self.a.post(url, json={"content":"From the owner"}).json()
        self.assertEqual(self.b.delete(url+f"/{owner_comment['id']}").status_code, 404)

    def test_comment_preview_is_bounded_ordered_and_checks_post_privacy(self):
        post = self.post()
        url = f"/api/v1/profile/posts/{post['id']}/comments"
        created = [self.b.post(url, json={"content":f"Reply {index}"}).json() for index in range(5)]
        response = self.anon.get(url+"?limit=3")
        self.assertEqual(response.status_code, 200)
        self.assertEqual([item["id"] for item in response.json()], [item["id"] for item in created[:3]])
        self.assertEqual(len(self.anon.get(url).json()), 5)
        for limit in (0, 101, -1):
            self.assertEqual(self.anon.get(url+f"?limit={limit}").status_code, 422)
        private = self.post("private")
        private_url = f"/api/v1/profile/posts/{private['id']}/comments"
        self.a.post(private_url, json={"content":"Only for me"})
        self.assertEqual(self.anon.get(private_url+"?limit=3").status_code, 404)
        self.assertEqual(self.b.get(private_url+"?limit=3").status_code, 404)
        self.assertEqual(len(self.a.get(private_url+"?limit=3").json()), 1)

    def test_comment_cannot_be_removed_through_another_post(self):
        first, second = self.post(), self.post()
        comment = self.b.post(f"/api/v1/profile/posts/{first['id']}/comments", json={"content":"Original post"}).json()
        response = self.a.delete(f"/api/v1/profile/posts/{second['id']}/comments/{comment['id']}")
        self.assertEqual(response.status_code, 404)
        self.assertEqual(len(self.a.get(f"/api/v1/profile/posts/{first['id']}/comments").json()), 1)

    def test_every_social_route_rechecks_privacy_after_friendship_revocation(self):
        post = self.post("friends")
        base = f"/api/v1/profile/posts/{post['id']}"
        self.assertEqual(self.b.get(base).status_code, 404)
        fid = self.friend()
        self.assertEqual(self.b.put(base+"/like").status_code, 200)
        comment = self.b.post(base+"/comments", json={"content":"Friends only"}).json()
        self.assertEqual(self.a.get(base).json()["likes_count"], 1)
        self.a.delete(f"/api/v1/friends/{fid}")
        calls = [("get",base,None),("get",base+"/comments",None),("put",base+"/like",None),
                 ("delete",base+"/like",None),("post",base+"/comments",{"content":"No longer allowed"}),
                 ("delete",base+f"/comments/{comment['id']}",None)]
        for method, path, body in calls:
            response = getattr(self.b, method)(path, **({"json":body} if body else {}))
            self.assertEqual(response.status_code, 404, (method, response.text))
        self.assertEqual(self.a.get(base).json()["comments_count"], 1)

    def test_privacy_edits_take_effect_and_delete_removes_conversations(self):
        post = self.post()
        base = f"/api/v1/profile/posts/{post['id']}"
        self.b.put(base+"/like")
        self.b.post(base+"/comments", json={"content":"A reply"})
        self.a.put(f"/api/v1/my/feed/{post['id']}", data={"payload":json.dumps({"content":"Private now", "visibility":"private"})})
        self.assertEqual(self.b.get(base).status_code, 404)
        self.assertEqual(self.anon.get(base+"/comments").status_code, 404)
        self.assertEqual(self.a.delete(f"/api/v1/my/posts/{post['id']}").status_code, 204)
        with self.sessions() as db:
            self.assertEqual(db.scalar(select(func.count()).select_from(ProfilePostLike)), 0)
            self.assertEqual(db.scalar(select(func.count()).select_from(ProfilePostComment)), 0)

    def test_profile_status_audio_respects_its_own_privacy_and_file_deletion(self):
        upload = self.a.post("/api/v1/my/files", data={"pinned":"false", "visibility":"friends"}, files={"file":("status.wav", AUDIO, "audio/wav")})
        self.assertEqual(upload.status_code, 201, upload.text)
        audio = upload.json()
        self.assertFalse(audio["pinned"])
        payload = {"full_name":"Alice", "status_text":"Working on myself", "status_audio_id":audio["id"],
                   "location":"Tomsk", "interests":"Art, music", "website":"https://example.org", "about":"A longer story"}
        response = self.a.put("/api/v1/my/profile", json=payload)
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["status_audio"]["id"], audio["id"])
        guest = self.anon.get("/api/v1/people/alice").json()
        self.assertEqual(guest["status_text"], payload["status_text"])
        self.assertIsNone(guest["status_audio"])
        self.assertIsNone(guest["status_audio_id"])
        self.assertEqual(guest["about"], payload["about"])
        fid = self.friend()
        self.assertEqual(self.b.get("/api/v1/people/alice").json()["status_audio"]["id"], audio["id"])
        self.assertEqual(self.b.get(audio["url"]).status_code, 200)
        self.a.delete(f"/api/v1/friends/{fid}")
        self.assertIsNone(self.b.get("/api/v1/people/alice").json()["status_audio"])
        self.assertEqual(self.b.get(audio["url"]).status_code, 404)
        # An older client editing just the name must not erase the status.
        self.a.put("/api/v1/my/profile", json={"full_name":"Alice new"})
        self.assertEqual(self.a.get("/api/v1/my/profile").json()["status_text"], payload["status_text"])
        self.assertEqual(self.a.delete(f"/api/v1/my/files/{audio['id']}").status_code, 204)
        self.assertIsNone(self.a.get("/api/v1/my/profile").json()["status_audio_id"])

    def test_status_rejects_foreign_non_audio_and_post_files_and_unsafe_website(self):
        foreign = self.b.post("/api/v1/my/files", files={"file":("foreign.wav", AUDIO)}).json()
        own_file = self.a.post("/api/v1/my/files", files={"file":("plain.txt", b"text")}).json()
        attached = self.a.post("/api/v1/my/feed", data={"payload":json.dumps({"content":"Music"})}, files=[("files",("attached.wav",AUDIO))]).json()["attachments"][0]
        for asset in (foreign, own_file, attached):
            response = self.a.put("/api/v1/my/profile", json={"full_name":"Alice", "status_audio_id":asset["id"]})
            self.assertEqual(response.status_code, 422, response.text)
        for value in ("javascript:alert(1)", "https://user:pass@example.org", "https://example.org/\nb"):
            self.assertEqual(self.a.put("/api/v1/my/profile", json={"full_name":"Alice", "website":value}).status_code, 422)

    def test_automatic_progress_advances_without_writes_and_legacy_checkin_does_not_double_count(self):
        pact = self.pact()
        self.assertEqual(pact["tracking_mode"], "automatic")
        self.assertEqual(pact["streak_days"], 1)
        self.assertEqual(pact["total_days"], 1)
        self.assertIsNone(pact["progress"])
        with self.sessions() as db:
            user = db.scalar(select(User).where(User.username == "alice"))
            record = db.get(Pact, pact["id"])
            tracking = db.get(PactTracking, (record.id, user.id))
            start = tracking.started_at.replace(tzinfo=timezone.utc)
            later = tracking_view(db, record, user.id, 420, now=start+timedelta(days=4))
            self.assertEqual(later["total_days"], 5)
            self.assertEqual(later["streak_days"], 5)
            db.add(PactCheckin(pact_id=record.id, user_id=user.id, day=(start+timedelta(hours=7)).date()))
            db.commit()
            self.assertEqual(tracking_view(db, record, user.id, 420, now=start+timedelta(days=4))["total_days"], 5)
            self.assertEqual(db.scalar(select(func.count()).select_from(PactCheckin)), 1)

    def test_break_is_today_only_idempotent_and_resumes_tomorrow_per_member(self):
        pact = self.pact()
        day = (datetime.now(timezone.utc)+timedelta(hours=7)).date()
        url = f"/api/v1/my/pacts/{pact['id']}/break"
        payload = {"day":day.isoformat(), "utc_offset_minutes":420}
        self.assertEqual(self.anon.post(url, json=payload).status_code, 401)
        self.assertEqual(self.b.post(url, json=payload).status_code, 404)
        for delta in (-1,1):
            self.assertEqual(self.a.post(url, json={**payload,"day":(day+timedelta(days=delta)).isoformat()}).status_code, 422)
        self.assertEqual(self.a.post(url, json={**payload,"utc_offset_minutes":900}).status_code, 422)
        self.assertEqual(self.a.get("/api/v1/my/pacts?utc_offset_minutes=900").status_code, 422)
        for _ in range(2):
            result = self.a.post(url, json=payload)
            self.assertEqual(result.status_code, 200, result.text)
            self.assertEqual(result.json()["streak_days"], 0)
            self.assertEqual(result.json()["total_days"], 0)
            self.assertEqual(result.json()["broken_days"], [day.isoformat()])
        with self.sessions() as db:
            user = db.scalar(select(User).where(User.username == "alice"))
            record = db.get(Pact, pact["id"])
            tomorrow = tracking_view(db, record, user.id, 420, now=datetime.now(timezone.utc)+timedelta(days=1))
            self.assertEqual(tomorrow["streak_days"], 1)
            self.assertEqual(tomorrow["total_days"], 1)
            self.assertEqual(db.scalar(select(func.count()).select_from(PactBreak)), 1)

    def test_tracking_preserves_old_history_and_does_not_backfill_unrecorded_days(self):
        pact = self.pact()
        now = datetime.now(timezone.utc)
        today = now.date()
        with self.sessions() as db:
            user = db.scalar(select(User).where(User.username == "alice"))
            record = db.get(Pact, pact["id"])
            record.created_at = now-timedelta(days=90)
            db.get(PactTracking, (record.id,user.id)).started_at = now
            db.add_all([PactCheckin(pact_id=record.id,user_id=user.id,day=today-timedelta(days=offset)) for offset in (1,2,40)])
            db.commit()
            result = tracking_view(db, record, user.id, 0, now=now)
            self.assertEqual(result["total_days"], 4)
            self.assertEqual(result["streak_days"], 3)
            db.add(PactBreak(pact_id=record.id,user_id=user.id,day=today))
            db.commit()
            result = tracking_view(db, record, user.id, 0, now=now)
            self.assertEqual(result["total_days"], 3)
            self.assertEqual(result["streak_days"], 0)

    def test_expiry_completion_and_cancellation_freeze_progress(self):
        pact = self.pact("common")
        with self.sessions() as db:
            user = db.scalar(select(User).where(User.username == "alice"))
            record = db.get(Pact, pact["id"])
            tracking = db.get(PactTracking, (record.id,user.id))
            start = tracking.started_at.replace(tzinfo=timezone.utc)
            result = tracking_view(db, record, user.id, now=start+timedelta(days=30))
            self.assertEqual(result["total_days"], 7)
            self.assertEqual(result["progress"], 100)
            record.deadline = None
            record.status = PactStatus.cancelled
            record.updated_at = start+timedelta(days=2)
            db.commit()
            frozen = tracking_view(db, record, user.id, now=start+timedelta(days=90))
            self.assertEqual(frozen["total_days"], 3)
            self.assertEqual(frozen["streak_days"], 3)
        self.assertEqual(self.a.post(f"/api/v1/my/pacts/{pact['id']}/break",json={"day":datetime.now(timezone.utc).date().isoformat()}).status_code,409)

    def test_joint_tracking_starts_on_acceptance_and_breaks_are_personal(self):
        response = self.a.post("/api/v1/requests", json={"recipient":"boris", "title":"Together", "description":"We keep this promise", "duration_days":7})
        self.assertEqual(response.status_code,201,response.text)
        self.assertEqual(self.a.get("/api/v1/my/pacts").json()[0]["total_days"],0)
        request = self.b.get("/api/v1/requests").json()[0]
        self.b.post(f"/api/v1/requests/{request['id']}/respond",json={"accept":True})
        for client in (self.a,self.b):
            self.assertEqual(client.get("/api/v1/my/pacts").json()[0]["total_days"],1)
        self.a.post(f"/api/v1/my/pacts/{request['pact_id']}/break",json={"day":datetime.now(timezone.utc).date().isoformat()})
        self.assertEqual(self.a.get("/api/v1/my/pacts").json()[0]["streak_days"],0)
        self.assertEqual(self.b.get("/api/v1/my/pacts").json()[0]["streak_days"],1)

    def test_break_in_final_partial_day_resets_even_when_finite_total_is_capped(self):
        pact = self.pact("common")
        start = datetime(2026,10,1,18,tzinfo=timezone.utc)
        before_expiry = start+timedelta(days=7,hours=-1)
        with self.sessions() as db:
            user = db.scalar(select(User).where(User.username == "alice"))
            record = db.get(Pact,pact["id"])
            record.created_at, record.deadline = start, start+timedelta(days=7)
            db.get(PactTracking,(record.id,user.id)).started_at = start
            db.add(PactBreak(pact_id=record.id,user_id=user.id,day=before_expiry.date()))
            db.commit()
            result = tracking_view(db,record,user.id,0,now=before_expiry)
            self.assertEqual(result["total_days"],7)
            self.assertEqual(result["streak_days"],0)
