"""Run: .venv/Scripts/python.exe -m unittest discover -s tests -v

Uses a fresh in-memory SQLite for every test; never reads pact.db.
"""
import os
os.environ["DATABASE_URL"] = "sqlite://"

import unittest
from datetime import date, datetime, timedelta, timezone

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.models import Calendar, CalendarEntry, CalendarEntryDetails, CalendarStyle, Comment, Pact, PactDetails, PactParticipant, PactRarity, PactStatus
from app.routers.workspace import finish_date


class WorkspaceTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        Base.metadata.create_all(self.engine)
        self.sessions = sessionmaker(bind=self.engine)
        def database():
            with self.sessions() as db:
                yield db
        app.dependency_overrides[get_db] = database
        self.a, self.b, self.anon = (TestClient(app) for _ in range(3))
        for client, name in [(self.a, "alice"), (self.b, "boris")]:
            response = client.post("/api/v1/auth/register", json={"username": name, "full_name": name.title(), "email": name+"@example.test", "password": "test-password-123"})
            self.assertEqual(response.status_code, 201, response.text)

    def tearDown(self):
        for client in [self.a, self.b, self.anon]:
            client.close()
        app.dependency_overrides.clear()
        self.engine.dispose()

    def test_only_own_pacts_can_be_created(self):
        self.assertEqual(self.anon.get("/api/v1/catalog").json(), [])
        self.assertEqual(self.anon.post("/api/v1/catalog/morning/join").status_code, 401)
        for template in ("morning", "invented"):
            self.assertEqual(self.a.post(f"/api/v1/catalog/{template}/join").status_code, 410)
        self.assertEqual(self.a.get("/api/v1/my/pacts").json(), [])
        for rarity, days in [("common", 7), ("legendary", None)]:
            payload = {"title": "Personal " + rarity, "description": "Practice every day", "rarity": rarity}
            response = self.a.post("/api/v1/my/pacts", json=payload)
            self.assertEqual(response.status_code, 201, response.text)
            self.assertEqual(response.json()["duration_days"], days)
            self.assertIsNone(response.json()["template_id"])
            self.assertEqual(self.a.post("/api/v1/my/pacts", json=payload).status_code, 409)
        self.assertEqual(self.b.get("/api/v1/my/pacts").json(), [])

    def test_calendar_month_and_leap_year(self):
        start = datetime(2024,1,31,tzinfo=timezone.utc)
        self.assertEqual(finish_date(start,"rare").date(),date(2024,2,29))
        self.assertEqual(finish_date(start.replace(month=2,day=29),"epic").date(),date(2025,2,28))

    def test_search_only_returns_member_pacts_and_preserves_historical_records(self):
        own = self.a.post("/api/v1/my/pacts",json={"title":"Unique private promise","description":"Unique daily conditions"}).json()
        self.b.post("/api/v1/my/pacts",json={"title":"Unique other promise","description":"Secret conditions"})
        results = self.a.get("/api/v1/search?kind=pacts&q=Unique").json()
        self.assertEqual([item["id"] for item in results],[own["id"]])
        self.assertEqual(results[0]["href"],f"/people/alice?pact={own['id']}#pacts")
        self.assertEqual(self.anon.get("/api/v1/search?kind=pacts&q=Unique").json(),[])
        uid = self.a.get("/api/v1/auth/me").json()["id"]
        with self.sessions() as db:
            old = Pact(title="Historical promise",description="Original conditions",creator_id=uid,rarity=PactRarity.common,status=PactStatus.active)
            db.add(old);db.flush()
            db.add_all([PactDetails(pact_id=old.id,template_id="walk",duration_days=7),PactParticipant(pact_id=old.id,user_id=uid),Comment(user_id=uid,template_id="walk",content="Historical comment")])
            db.commit()
            old_id = old.id
        old = self.a.get(f"/api/v1/pacts/{old_id}").json()
        self.assertEqual(old["description"],"Original conditions")
        self.assertEqual(old["category"],"Тело")
        self.assertEqual(old["template_id"],"walk")
        archive = self.anon.get("/api/v1/forum?template_id=walk").json()
        self.assertEqual(archive["comments"][0]["content"],"Historical comment")
        self.assertTrue(archive["comments"][0]["topic_title"])
        self.assertEqual(self.a.post("/api/v1/catalog/walk/join").status_code,410)
        self.assertEqual(self.a.get(f"/api/v1/pacts/{old_id}").json(),old)

    def test_checkin_uses_local_day_and_exact_expiry_time(self):
        pact = self.a.post("/api/v1/my/pacts", json={"title":"Morning practice", "description":"Practice every morning", "rarity":"common"}).json()
        utc_now = datetime.now(timezone.utc)
        day = (utc_now+timedelta(hours=7)).date().isoformat()
        response = self.a.post(f"/api/v1/my/pacts/{pact['id']}/checkin",json={"day":day,"utc_offset_minutes":420})
        self.assertEqual(response.status_code,200,response.text)
        self.assertEqual(response.json()["checkins"],[day])
        self.assertEqual(self.a.post(f"/api/v1/my/pacts/{pact['id']}/complete").status_code,409)
        with self.sessions() as db:
            record = db.get(Pact,pact["id"])
            record.deadline = utc_now-timedelta(seconds=1)
            db.commit()
        self.assertEqual(self.a.post(f"/api/v1/my/pacts/{pact['id']}/checkin",json={"day":day,"utc_offset_minutes":420}).status_code,409)
        self.assertEqual(self.a.post(f"/api/v1/my/pacts/{pact['id']}/complete").status_code,200)

    def test_whitespace_inputs_and_duplicate_normalized_invitees(self):
        self.assertEqual(self.a.post("/api/v1/notes",json={"title":"  ","content":"text"}).status_code,422)
        self.assertEqual(self.a.post("/api/v1/calendars",json={"name":"  ","color":"#aabbcc"}).status_code,422)
        response = self.a.post("/api/v1/notes",json={"title":"Invited","content":"Text","visibility":"invited","invitees":["boris","@boris"]})
        self.assertEqual(response.status_code,201,response.text)
        self.assertEqual(response.json()["invitees"],["boris"])

    def test_checkin_is_per_user_per_day_and_not_future(self):
        pact = self.a.post("/api/v1/my/pacts", json={"title":"Morning practice", "description":"Practice every morning", "rarity":"common"}).json()
        day = datetime.now(timezone.utc).date().isoformat()
        for _ in range(2):
            response = self.a.post(f"/api/v1/my/pacts/{pact['id']}/checkin",json={"day":day})
            self.assertEqual(response.status_code,200,response.text)
            self.assertEqual(response.json()["checkins"],[day])
            self.assertEqual(response.json()["progress"],14)
        self.assertEqual(self.b.post(f"/api/v1/my/pacts/{pact['id']}/checkin",json={"day":day}).status_code,404)
        future = (datetime.now(timezone.utc).date()+timedelta(days=3)).isoformat()
        self.assertEqual(self.a.post(f"/api/v1/my/pacts/{pact['id']}/checkin",json={"day":future}).status_code,422)

    def test_joint_acceptance_and_private_discussion(self):
        response = self.a.post("/api/v1/requests",json={"recipient":"boris","title":"Read together","description":"Read twenty pages every day.","duration_days":12})
        self.assertEqual(response.status_code,201,response.text)
        pact_id = response.json()["id"]
        self.assertEqual(self.a.get("/api/v1/my/pacts").json()[0]["status"],"draft")
        self.assertEqual(self.b.get("/api/v1/my/pacts").json(),[])
        request_id = self.b.get("/api/v1/requests").json()[0]["id"]
        self.assertEqual(self.a.post(f"/api/v1/requests/{request_id}/respond",json={"accept":True}).status_code,404)
        self.assertEqual(self.b.post(f"/api/v1/requests/{request_id}/respond",json={"accept":True}).status_code,200)
        self.assertEqual(self.b.post(f"/api/v1/requests/{request_id}/respond",json={"accept":True}).status_code,409)
        mine = self.b.get("/api/v1/my/pacts").json()[0]
        self.assertEqual(mine["status"],"active")
        self.assertEqual(len(mine["members"]),2)
        self.assertEqual(mine["duration_days"],12)
        response = self.a.post("/api/v1/forum",json={"pact_id":pact_id,"content":"Private words"})
        self.assertEqual(response.status_code,201,response.text)
        self.assertEqual(len(self.b.get(f"/api/v1/forum?pact_id={pact_id}").json()["comments"]),1)
        self.assertEqual(self.anon.get("/api/v1/forum").json()["comments"],[])
        self.assertEqual(self.anon.get(f"/api/v1/forum?pact_id={pact_id}").status_code,401)

    def test_declined_request_does_not_activate(self):
        self.a.post("/api/v1/requests",json={"recipient":"boris","title":"Read together","description":"Read twenty pages daily.","duration_days":12})
        request_id = self.b.get("/api/v1/requests").json()[0]["id"]
        self.b.post(f"/api/v1/requests/{request_id}/respond",json={"accept":False})
        self.assertEqual(self.a.get("/api/v1/my/pacts").json()[0]["status"],"cancelled")
        self.assertEqual(self.b.get("/api/v1/my/pacts").json(),[])

    def test_note_visibility_search_and_revocation(self):
        ids = {}
        for visibility in ["private","invited","public"]:
            response = self.a.post("/api/v1/notes",json={"title":"Unique thought "+visibility,"content":"Unique text", "visibility":visibility,"invitees":["boris"]})
            self.assertEqual(response.status_code,201,response.text)
            ids[visibility] = response.json()["id"]
        self.assertEqual(self.b.get(f"/api/v1/notes/{ids['private']}").status_code,404)
        self.assertEqual(self.anon.get(f"/api/v1/notes/{ids['invited']}").status_code,404)
        self.assertEqual(self.b.get(f"/api/v1/notes/{ids['invited']}").status_code,200)
        self.assertEqual(self.anon.get(f"/api/v1/notes/{ids['public']}").status_code,200)
        self.assertEqual(len(self.b.get("/api/v1/search?kind=notes&q=Unique").json()),2)
        self.assertEqual(len(self.anon.get("/api/v1/search?kind=notes&q=Unique").json()),1)
        public_profile = self.anon.get("/api/v1/people/alice").json()
        self.assertNotIn("email",public_profile["user"])
        self.assertEqual(len(public_profile["notes"]),1)
        self.assertEqual(self.b.put(f"/api/v1/notes/{ids['invited']}",json={"title":"Stolen","content":"No"}).status_code,404)
        response = self.a.put(f"/api/v1/notes/{ids['invited']}",json={"title":"Unique thought invited","content":"Unique text","visibility":"private"})
        self.assertEqual(response.status_code,200,response.text)
        self.assertEqual(self.b.get(f"/api/v1/notes/{ids['invited']}").status_code,404)
        self.assertEqual(self.b.get("/api/v1/notes").json(),[])

    def test_calendar_limit_unique_colors_and_ownership(self):
        first = self.a.post("/api/v1/calendars",json={"name":"Calendar","color":"#AABBCC"})
        self.assertEqual(first.status_code,201,first.text)
        cid = first.json()["id"]
        self.assertEqual(first.json()["color"],"#aabbcc")
        self.assertEqual(self.a.post("/api/v1/calendars",json={"name":"Duplicate","color":"#aabbcc"}).status_code,409)
        for i in range(9):
            self.assertEqual(self.a.post("/api/v1/calendars",json={"name":str(i),"color":f"#{i:06x}"}).status_code,201)
        self.assertEqual(self.a.post("/api/v1/calendars",json={"name":"Over limit","color":"#123456"}).status_code,409)
        self.assertEqual(self.b.get("/api/v1/calendars").json(),[])
        payload = {"calendar_id":cid,"title":"Secret event","day":"2026-10-19"}
        self.assertEqual(self.b.post("/api/v1/calendar-entries",json=payload).status_code,404)
        entry = self.a.post("/api/v1/calendar-entries",json=payload)
        self.assertEqual(entry.status_code,201,entry.text)
        self.assertEqual(self.b.delete(f"/api/v1/calendar-entries/{entry.json()['id']}").status_code,404)
        self.assertEqual(self.b.get("/api/v1/calendar-entries?start=2026-10-01&end=2026-10-31").json(),[])
        self.assertEqual(self.a.delete(f"/api/v1/calendars/{cid}").status_code,204)
        self.assertEqual(self.a.get("/api/v1/calendar-entries?start=2026-10-01&end=2026-10-31").json(),[])

    def test_personal_forum_trending_newest_first_and_no_leaks(self):
        pact = self.a.post("/api/v1/my/pacts", json={"title":"Private practice", "description":"Practice every morning"}).json()
        for content in ["First comment", "Second comment"]:
            self.assertEqual(self.a.post("/api/v1/forum", json={"pact_id":pact["id"], "content":content}).status_code, 201)
        forum = self.a.get("/api/v1/forum").json()
        self.assertEqual(forum["comments"][0]["content"], "Second comment")
        self.assertEqual(forum["trending"][0]["count"], 2)
        for client in (self.anon, self.b):
            data = client.get("/api/v1/forum").json()
            self.assertEqual(data["comments"], [])
            self.assertEqual(data["trending"], [])
            self.assertEqual(data["topics"], [])
        self.assertEqual(self.a.post("/api/v1/forum", json={"template_id":"morning", "content":"Archived"}).status_code, 410)
        self.assertEqual(self.a.post("/api/v1/forum", json={"pact_id":pact["id"], "content":"   "}).status_code, 422)

    def test_calendar_themes_and_individual_access(self):
        response = self.a.post("/api/v1/calendars",json={"name":"Study","color":"#91a5df","theme":"grid"})
        self.assertEqual(response.status_code,201,response.text)
        calendar = response.json()
        self.assertEqual(calendar["theme"],"grid")
        self.assertEqual(self.a.get(f"/api/v1/calendars/{calendar['id']}").json(),calendar)
        self.assertEqual(self.b.get(f"/api/v1/calendars/{calendar['id']}").status_code,404)
        self.assertEqual(self.anon.get(f"/api/v1/calendars/{calendar['id']}").status_code,401)
        response = self.a.put(f"/api/v1/calendars/{calendar['id']}",json={"name":"Reading","color":"#E4B563","theme":"journal"})
        self.assertEqual(response.status_code,200,response.text)
        self.assertEqual(response.json()["name"],"Reading")
        self.assertEqual(response.json()["theme"],"journal")
        self.assertEqual(response.json()["color"],"#e4b563")
        self.assertEqual(self.b.put(f"/api/v1/calendars/{calendar['id']}",json={"name":"Stolen","color":"#aabbcc"}).status_code,404)
        self.assertEqual(self.a.post("/api/v1/calendars",json={"name":"Invalid","color":"#abcabc","theme":"unknown"}).status_code,422)

    def test_task_planning_completion_reopen_and_move(self):
        first = self.a.post("/api/v1/calendars",json={"name":"Study","color":"#91a5df"}).json()
        second = self.a.post("/api/v1/calendars",json={"name":"Personal","color":"#e4b563"}).json()
        response = self.a.post("/api/v1/calendar-entries",json={"calendar_id":first["id"],"title":"Finish a chapter","day":"2026-10-20","kind":"task","description":"Read and write notes","start_time":"14:30","priority":"high"})
        self.assertEqual(response.status_code,201,response.text)
        task = response.json()
        self.assertEqual(task["kind"],"task")
        self.assertEqual(task["start_time"],"14:30")
        self.assertFalse(task["completed"])
        for completed in [True,False]:
            response = self.a.patch(f"/api/v1/calendar-entries/{task['id']}",json={"completed":completed})
            self.assertEqual(response.status_code,200,response.text)
            self.assertEqual(response.json()["completed"],completed)
            self.assertEqual(response.json()["description"],"Read and write notes")
        response = self.a.patch(f"/api/v1/calendar-entries/{task['id']}",json={"calendar_id":second["id"],"day":"2026-10-22","title":"Moved task"})
        self.assertEqual(response.status_code,200,response.text)
        self.assertEqual(response.json()["calendar_id"],second["id"])
        self.assertEqual(response.json()["day"],"2026-10-22")
        self.assertEqual(self.a.get(f"/api/v1/calendar-entries?start=2026-10-01&end=2026-10-31&calendar_id={first['id']}").json(),[])
        self.assertEqual(len(self.a.get(f"/api/v1/calendar-entries?start=2026-10-01&end=2026-10-31&calendar_id={second['id']}").json()),1)

    def test_plans_cannot_be_moved_into_or_read_from_another_users_calendar(self):
        mine = self.a.post("/api/v1/calendars",json={"name":"Mine","color":"#91a5df"}).json()
        foreign = self.b.post("/api/v1/calendars",json={"name":"Foreign","color":"#91a5df"}).json()
        entry = self.a.post("/api/v1/calendar-entries",json={"calendar_id":mine["id"],"title":"Private plan","day":"2026-10-20","kind":"task"}).json()
        url = f"/api/v1/calendar-entries/{entry['id']}"
        self.assertEqual(self.b.get(url).status_code,404)
        self.assertEqual(self.b.patch(url,json={"completed":True}).status_code,404)
        self.assertEqual(self.b.delete(url).status_code,404)
        self.assertEqual(self.a.patch(url,json={"calendar_id":foreign["id"]}).status_code,404)
        self.assertEqual(self.a.get(url).json()["calendar_id"],mine["id"])
        self.assertEqual(self.a.get(f"/api/v1/calendar-entries?start=2026-10-01&end=2026-10-31&calendar_id={foreign['id']}").status_code,404)

    def test_event_time_validation_and_non_task_completion(self):
        calendar = self.a.post("/api/v1/calendars",json={"name":"Events","color":"#91a5df"}).json()
        base = {"calendar_id":calendar["id"],"title":"Meeting","day":"2026-10-20","kind":"event"}
        for times in [{"start_time":"25:00"},{"end_time":"14:00"},{"start_time":"15:00","end_time":"14:00"},{"start_time":"15:00","end_time":"15:00"}]:
            self.assertEqual(self.a.post("/api/v1/calendar-entries",json={**base,**times}).status_code,422)
        event = self.a.post("/api/v1/calendar-entries",json={**base,"start_time":"14:00","end_time":"15:00"})
        self.assertEqual(event.status_code,201,event.text)
        self.assertEqual(self.a.patch(f"/api/v1/calendar-entries/{event.json()['id']}",json={"completed":True}).status_code,422)
        self.assertEqual(self.a.get("/api/v1/calendar-entries?start=2026-10-31&end=2026-10-01").status_code,422)
        self.assertEqual(self.a.get("/api/v1/calendar-entries?start=2025-01-01&end=2026-10-01").status_code,422)

    def test_old_calendar_entries_survive_and_can_become_tasks(self):
        user_id = self.a.get("/api/v1/auth/me").json()["id"]
        with self.sessions() as db:
            calendar = Calendar(user_id=user_id,name="Legacy calendar",color="#abcdef")
            db.add(calendar); db.flush()
            entry = CalendarEntry(calendar_id=calendar.id,title="Original note",day=date(2026,10,20))
            db.add(entry); db.commit()
            cid, eid = calendar.id, entry.id
        self.assertEqual(self.a.get(f"/api/v1/calendars/{cid}").json()["theme"],"classic")
        entry = self.a.get(f"/api/v1/calendar-entries/{eid}").json()
        self.assertEqual(entry["kind"],"note")
        self.assertEqual(entry["title"],"Original note")
        response = self.a.patch(f"/api/v1/calendar-entries/{eid}",json={"kind":"task","completed":True})
        self.assertEqual(response.status_code,200,response.text)
        self.assertTrue(response.json()["completed"])
        self.assertEqual(response.json()["title"],"Original note")

    def test_calendar_deletion_removes_planning_metadata_without_touching_other_calendars(self):
        first = self.a.post("/api/v1/calendars",json={"name":"First","color":"#91a5df","theme":"grid"}).json()
        second = self.a.post("/api/v1/calendars",json={"name":"Second","color":"#e4b563"}).json()
        removed = self.a.post("/api/v1/calendar-entries",json={"calendar_id":first["id"],"title":"Task","day":"2026-10-20","kind":"task"}).json()
        kept = self.a.post("/api/v1/calendar-entries",json={"calendar_id":second["id"],"title":"Keep","day":"2026-10-20"}).json()
        self.assertEqual(self.a.delete(f"/api/v1/calendars/{first['id']}").status_code,204)
        self.assertEqual(self.a.get(f"/api/v1/calendar-entries/{removed['id']}").status_code,404)
        self.assertEqual(self.a.get(f"/api/v1/calendar-entries/{kept['id']}").status_code,200)
        with self.sessions() as db:
            self.assertIsNone(db.get(CalendarStyle,first["id"]))
            self.assertIsNone(db.get(CalendarEntryDetails,removed["id"]))
        self.assertEqual(self.a.delete(f"/api/v1/calendar-entries/{kept['id']}").status_code,204)
        with self.sessions() as db:
            self.assertIsNone(db.get(CalendarEntryDetails,kept["id"]))

    def test_legacy_endpoints_do_not_bypass_auth_or_ownership(self):
        self.assertEqual(self.anon.get("/api/v1/users").status_code,401)
        self.assertEqual(self.anon.get("/api/v1/pacts").status_code,401)
        self.assertEqual(self.anon.post("/api/v1/pacts",json={"title":"Bypass"}).status_code,401)
        pact = self.a.post("/api/v1/my/pacts", json={"title":"Morning practice", "description":"Practice every morning", "rarity":"common"}).json()
        self.assertEqual(self.b.get(f"/api/v1/pacts/{pact['id']}").status_code,404)
        self.assertEqual(self.b.patch(f"/api/v1/pacts/{pact['id']}",json={"status":"completed"}).status_code,404)
        self.assertNotIn("email",self.a.get("/api/v1/users").json()[0])


if __name__ == "__main__":
    unittest.main()
