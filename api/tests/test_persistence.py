import json
import os
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from threading import Barrier

os.environ["DATABASE_URL"] = "sqlite://"

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.database import Base, get_db
from app.routers import auth, feed, workspace


def isolated_app(engine):
    application = FastAPI()
    for router in (auth.router,workspace.router,feed.router):
        application.include_router(router,prefix="/api/v1")
    def database():
        with Session(engine) as db:
            yield db
    application.dependency_overrides[get_db] = database
    return application


class PersistenceTests(unittest.TestCase):
    def test_parallel_creation_keeps_capacity_and_parallel_checkin_is_idempotent(self):
        with tempfile.TemporaryDirectory(prefix="nen-concurrency-") as folder:
            engine = create_engine("sqlite:///"+Path(folder,"race.sqlite3").as_posix(),connect_args={"check_same_thread":False})
            Base.metadata.create_all(engine)
            application = isolated_app(engine)
            try:
                with TestClient(application) as first,TestClient(application) as second:
                    response = first.post("/api/v1/auth/register",json={"username":"parallel","full_name":"Parallel user","email":"parallel@example.test","password":"test-password-123"})
                    self.assertEqual(response.status_code,201,response.text)
                    second.cookies.set(auth.COOKIE_NAME,first.cookies.get(auth.COOKIE_NAME))
                    for index in range(2):
                        response = first.post("/api/v1/my/pacts",json={"title":f"Existing {index}","description":"Daily practice","rarity":"common"})
                        self.assertEqual(response.status_code,201,response.text)
                    gate = Barrier(2)
                    def create(index,client):
                        gate.wait(timeout=10)
                        return client.post("/api/v1/my/pacts",json={"title":f"Concurrent {index}","description":"Daily practice","rarity":"common"})
                    with ThreadPoolExecutor(max_workers=2) as executor:
                        futures = [executor.submit(create,index,client) for index,client in enumerate((first,second))]
                        results = [future.result() for future in futures]
                    self.assertEqual(sorted(result.status_code for result in results),[201,409])
                    pacts = first.get("/api/v1/my/pacts").json()
                    self.assertEqual(len(pacts),3)
                    pid = pacts[0]["id"]
                    day = datetime.now(timezone.utc).date().isoformat()
                    with ThreadPoolExecutor(max_workers=2) as executor:
                        results = list(executor.map(lambda client:client.post(f"/api/v1/my/pacts/{pid}/checkin",json={"day":day}),(first,second)))
                    self.assertTrue(all(result.status_code == 200 for result in results))
                    updated = next(pact for pact in first.get("/api/v1/my/pacts").json() if pact["id"] == pid)
                    self.assertEqual(updated["checkins"],[day])
            finally:
                engine.dispose()

    def test_new_application_and_reopened_sqlite_keep_session_progress_and_file(self):
        with tempfile.TemporaryDirectory(prefix="nen-persistence-") as folder:
            url = "sqlite:///"+Path(folder,"test.sqlite3").as_posix()
            first_engine = create_engine(url,connect_args={"check_same_thread":False})
            Base.metadata.create_all(first_engine)
            with TestClient(isolated_app(first_engine)) as client:
                response = client.post("/api/v1/auth/register",json={"username":"persistent","full_name":"Persistent user","email":"persistent@example.test","password":"test-password-123"})
                self.assertEqual(response.status_code,201,response.text)
                token = client.cookies.get(auth.COOKIE_NAME)
                response = client.post("/api/v1/my/pacts",json={"title":"Persistent pact","description":"Practice each day","category":"Разум","rarity":"common"})
                self.assertEqual(response.status_code,201,response.text)
                pid = response.json()["id"]
                day = datetime.now(timezone.utc).date().isoformat()
                response = client.post(f"/api/v1/my/pacts/{pid}/checkin",json={"day":day})
                self.assertEqual(response.status_code,200,response.text)
                response = client.post("/api/v1/my/feed",data={"payload":json.dumps({"content":"Persistent post","pin_new":True})},files=[("files",("saved.bin",b"persistent bytes","application/octet-stream"))])
                self.assertEqual(response.status_code,201,response.text)
                asset = response.json()["attachments"][0]
            first_engine.dispose()
            second_engine = create_engine(url,connect_args={"check_same_thread":False})
            try:
                with TestClient(isolated_app(second_engine)) as client:
                    client.cookies.set(auth.COOKIE_NAME,token)
                    self.assertEqual(client.get("/api/v1/auth/me").json()["username"],"persistent")
                    pact = client.get("/api/v1/my/pacts").json()[0]
                    self.assertEqual(pact["id"],pid)
                    self.assertEqual(pact["checkins"],[day])
                    self.assertEqual(pact["progress"],14)
                    self.assertEqual(client.get(asset["url"]).content,b"persistent bytes")
                    self.assertTrue(client.get("/api/v1/my/files").json()[0]["pinned"])
                    self.assertEqual(client.get("/api/v1/forum/posts?scope=mine").json()[0]["content"],"Persistent post")
                    self.assertEqual(client.post(f"/api/v1/my/pacts/{pid}/checkin",json={"day":day}).json()["checkins"],[day])
            finally:
                second_engine.dispose()
