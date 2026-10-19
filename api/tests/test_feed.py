import base64
import json
import unittest
from unittest.mock import patch

from sqlalchemy import func, select

import test_workspace
from app.models import ProfileFile, ProfilePost
from test_community import PNG

IMAGE = base64.b64decode(PNG.split(",")[1])
AUDIO = b"RIFF" + (100).to_bytes(4,"little") + b"WAVE" + b"example audio content" * 4


class FeedTests(unittest.TestCase):
    def setUp(self):
        test_workspace.WorkspaceTests.setUp(self)

    def tearDown(self):
        test_workspace.WorkspaceTests.tearDown(self)

    def post(self, files=None, **payload):
        response = self.a.post("/api/v1/my/feed", data={"payload":json.dumps({"content":"A post with attachments",**payload})}, files=files or [])
        self.assertEqual(response.status_code,201,response.text)
        return response.json()

    def upload(self, name="file.any", content=b"arbitrary bytes", visibility="private"):
        return self.a.post("/api/v1/my/files",data={"visibility":visibility},files={"file":(name,content,"application/octet-stream")})

    def test_forum_feed_uses_post_privacy_and_revokes_friend_access(self):
        posts = {visibility:self.post(visibility=visibility, title="Only "+visibility,
                    files=[("files",(visibility+".png",IMAGE,"image/png"))]) for visibility in ("public","friends","private")}
        def ids(client):
            return {post["id"] for post in client.get("/api/v1/forum/posts").json()}
        self.assertEqual(ids(self.a), {post["id"] for post in posts.values()})
        self.assertEqual(ids(self.anon), {posts["public"]["id"]})
        self.assertEqual(ids(self.b), {posts["public"]["id"]})
        fid = self.a.post("/api/v1/friends",json={"username":"boris"}).json()["id"]
        self.assertEqual(ids(self.b), {posts["public"]["id"]})
        self.b.post(f"/api/v1/friends/{fid}/respond",json={"accept":True})
        self.assertEqual(ids(self.b), {posts["public"]["id"],posts["friends"]["id"]})
        feed = self.b.get("/api/v1/forum/posts").json()
        self.assertEqual(feed[0]["id"], posts["friends"]["id"])
        self.assertEqual(feed[0]["author"]["username"], "alice")
        self.assertNotIn("email", feed[0]["author"])
        file = posts["friends"]["attachments"][0]
        self.assertEqual(self.b.get(file["url"]).status_code, 200)
        self.assertEqual(self.anon.get(file["url"]).status_code, 404)
        # Both orientations of a friendship use the same policy.
        reverse = self.b.post("/api/v1/my/feed",data={"payload":json.dumps({"content":"Boris friends post","visibility":"friends"})}).json()
        self.assertIn(reverse["id"], ids(self.a))
        self.b.delete(f"/api/v1/friends/{fid}")
        self.assertEqual(ids(self.b), {posts["public"]["id"],reverse["id"]})
        self.assertNotIn(reverse["id"], ids(self.a))
        self.assertEqual(self.b.get(file["url"]).status_code, 404)

    def test_forum_reflects_edits_and_deleted_posts_without_duplicate_copies(self):
        post = self.post(visibility="public",files=[("files",("picture.png",IMAGE,"image/png"))])
        file = post["attachments"][0]
        self.assertEqual(len(self.anon.get("/api/v1/forum/posts").json()),1)
        updated = self.a.put(f"/api/v1/my/feed/{post['id']}",data={"payload":json.dumps({"content":"Now private","visibility":"private","keep_ids":[file["id"]]})})
        self.assertEqual(updated.status_code,200,updated.text)
        self.assertEqual(self.anon.get("/api/v1/forum/posts").json(),[])
        self.assertEqual(self.b.get("/api/v1/forum/posts").json(),[])
        self.assertEqual(self.anon.get(file["url"]).status_code,404)
        own = self.a.get("/api/v1/forum/posts").json()
        self.assertEqual(len(own),1)
        self.assertEqual(own[0]["id"],post["id"])
        self.assertEqual(own[0]["content"],"Now private")
        self.a.delete(f"/api/v1/my/posts/{post['id']}")
        self.assertEqual(self.a.get("/api/v1/forum/posts").json(),[])

    def test_forum_filters_before_limit_and_includes_legacy_posts(self):
        response = self.a.post("/api/v1/my/posts",json={"kind":"image","title":"Legacy public","content":"Existing post","visibility":"public","image_data":PNG})
        self.assertEqual(response.status_code,201,response.text)
        public = response.json()
        owner_id = self.b.get("/api/v1/auth/me").json()["id"]
        with self.sessions() as db:
            db.add_all([ProfilePost(user_id=owner_id,title=f"Hidden {index}",content="Secret",visibility="private") for index in range(110)])
            db.commit()
        feed = self.anon.get("/api/v1/forum/posts").json()
        self.assertEqual([post["id"] for post in feed],[public["id"]])
        self.assertEqual(feed[0]["title"],"Legacy public")
        self.assertEqual(self.anon.get(feed[0]["image_url"]).status_code,200)

    def test_post_combines_images_audio_and_arbitrary_files(self):
        post = self.post(files=[("files",("image.png",IMAGE,"image/png")),("files",("music.wav",AUDIO,"audio/wav")),("files",("project.custom",b"arbitrary binary", "application/octet-stream"))])
        self.assertEqual(post["kind"],"post")
        self.assertEqual([f["kind"] for f in post["attachments"]],["image","audio","file"])
        profile = self.a.get("/api/v1/my/profile").json()
        self.assertEqual(profile["posts"][0]["attachments"],post["attachments"])
        file = post["attachments"][2]
        self.assertEqual(self.a.get(file["url"]).content,b"arbitrary binary")
        self.assertEqual(self.anon.get(file["url"]).status_code,404)

    def test_real_file_size_boundary_and_rejection_leave_no_partial_file(self):
        size = 25*1024*1024
        content = b"x"*size
        accepted = self.upload("boundary.bin",content)
        self.assertEqual(accepted.status_code,201,accepted.text)
        file = accepted.json()
        self.assertEqual(file["size"],size)
        self.assertEqual(int(self.a.head(file["url"]).headers["content-length"]),size)
        part = self.a.get(file["url"],headers={"Range":"bytes=0-2"})
        self.assertEqual(part.status_code,206)
        self.assertEqual(part.content,b"xxx")
        rejected = self.upload("too-large.bin",content+b"x")
        self.assertEqual(rejected.status_code,413,rejected.text)
        self.assertEqual(len(self.a.get("/api/v1/my/files").json()),1)

    def test_ten_post_attachments_allowed_and_eleventh_rejected_atomically(self):
        files = [("files",(f"file-{index}.bin",b"file bytes","application/octet-stream")) for index in range(11)]
        post = self.post(files=files[:10])
        self.assertEqual(len(post["attachments"]),10)
        response = self.a.post("/api/v1/my/feed",data={"payload":json.dumps({"content":"Eleven files"})},files=files)
        self.assertEqual(response.status_code,422,response.text)
        self.assertEqual(len(self.a.get("/api/v1/my/profile").json()["posts"]),1)
        self.assertEqual(len(self.a.get("/api/v1/my/files").json()),10)

    def test_pin_limit_is_ten_across_standalone_and_post_files(self):
        for index in range(9):
            response = self.upload(f"file-{index}.bin")
            self.assertEqual(response.status_code,201,response.text)
        post = self.post(files=[("files",("music.wav",AUDIO,"audio/wav"))],pin_new=True)
        self.assertTrue(post["attachments"][0]["pinned"])
        self.assertEqual(len(self.a.get("/api/v1/my/profile").json()["pins"]),10)
        self.assertEqual(self.upload("eleventh.zip").status_code,409)
        before = len(self.a.get("/api/v1/my/profile").json()["posts"])
        failure = self.a.post("/api/v1/my/feed", data={"payload":json.dumps({"content":"Overflow","pin_new":True})},files=[("files",("new.txt",b"new","text/plain"))])
        self.assertEqual(failure.status_code,409,failure.text)
        self.assertEqual(len(self.a.get("/api/v1/my/profile").json()["posts"]),before)
        first = post["attachments"][0]
        self.assertEqual(self.a.put(f"/api/v1/my/files/{first['id']}",json={"pinned":False}).status_code,200)
        self.assertEqual(self.upload("replacement.txt").status_code,201)
        self.assertEqual(self.a.put(f"/api/v1/my/files/{first['id']}",json={"pinned":True}).status_code,409)

    def test_permissions_visibility_and_friend_revocation_cover_pins_and_files(self):
        file = self.upload(visibility="friends").json()
        self.assertEqual(self.b.get(file["url"]).status_code,404)
        fid = self.a.post("/api/v1/friends",json={"username":"boris"}).json()["id"]
        self.b.post(f"/api/v1/friends/{fid}/respond",json={"accept":True})
        self.assertEqual(self.b.get(file["url"]).status_code,200)
        self.assertEqual(len(self.b.get("/api/v1/people/alice").json()["pins"]),1)
        self.assertEqual(self.b.put(f"/api/v1/my/files/{file['id']}",json={"pinned":False}).status_code,404)
        self.assertEqual(self.b.delete(f"/api/v1/my/files/{file['id']}").status_code,404)
        self.assertEqual(self.anon.get("/api/v1/my/files").status_code,401)
        self.b.delete(f"/api/v1/friends/{fid}")
        self.assertEqual(self.b.get(file["url"]).status_code,404)
        self.assertEqual(self.b.get("/api/v1/people/alice").json()["pins"],[])

    def test_range_head_and_download_for_audio(self):
        file = self.upload("song.wav",AUDIO,"public").json()
        head = self.anon.head(file["url"])
        self.assertEqual(head.status_code,200)
        self.assertEqual(head.content,b"")
        self.assertEqual(int(head.headers["content-length"]),len(AUDIO))
        part = self.anon.get(file["url"],headers={"Range":"bytes=3-8"})
        self.assertEqual(part.status_code,206)
        self.assertEqual(part.content,AUDIO[3:9])
        self.assertEqual(part.headers["content-range"],f"bytes 3-8/{len(AUDIO)}")
        tail = self.anon.get(file["url"],headers={"Range":"bytes=-5"})
        self.assertEqual(tail.content,AUDIO[-5:])
        self.assertEqual(self.anon.get(file["url"],headers={"Range":"bytes=9999-"}).status_code,416)
        self.assertEqual(self.anon.get(file["url"],headers={"Range":"bytes=0-1,3-4"}).status_code,416)
        download = self.anon.get(file["download_url"])
        self.assertIn("attachment",download.headers["content-disposition"])
        self.assertEqual(download.headers["content-type"],"application/octet-stream")

    def test_html_svg_and_unusual_filenames_are_downloaded_without_execution(self):
        for name, content in [("../../evil.html",b"<script>alert(1)</script>"),("picture.svg",b"<svg onload='alert(1)'/>"),("..\\notes\r\n.txt",b"plain text")]:
            file = self.upload(name,content,"public").json()
            response = self.anon.get(file["url"])
            self.assertEqual(file["kind"],"file")
            self.assertNotIn("/",file["name"])
            self.assertNotIn("\\",file["name"])
            self.assertNotIn("\r",file["name"])
            self.assertEqual(response.headers["content-type"],"application/octet-stream")
            self.assertIn("attachment",response.headers["content-disposition"])
            self.assertEqual(response.headers["x-content-type-options"],"nosniff")
            self.assertIn("sandbox",response.headers["content-security-policy"])

    def test_edit_retains_reorders_and_removes_attachments_atomically(self):
        post = self.post(files=[("files",("one.bin",b"1","application/octet-stream")),("files",("two.bin",b"22","application/octet-stream"))],pin_new=True)
        one,two = post["attachments"]
        reorder = self.a.put(f"/api/v1/my/feed/{post['id']}",data={"payload":json.dumps({"content":"Reordered","keep_ids":[two["id"],one["id"]]})})
        self.assertEqual([file["id"] for file in reorder.json()["attachments"]],[two["id"],one["id"]])
        response = self.a.put(f"/api/v1/my/feed/{post['id']}",data={"payload":json.dumps({"content":"Edited","keep_ids":[two["id"]],"visibility":"public"})})
        self.assertEqual(response.status_code,200,response.text)
        self.assertEqual([f["id"] for f in response.json()["attachments"]],[two["id"]])
        self.assertEqual(self.a.get(one["url"]).status_code,404)
        self.assertEqual(self.anon.get(two["url"]).status_code,200)
        self.assertEqual(len(self.anon.get("/api/v1/people/alice").json()["pins"]),1)
        foreign = self.b.post("/api/v1/my/files",files={"file":("foreign",b"x")}).json()
        invalid = self.a.put(f"/api/v1/my/feed/{post['id']}",data={"payload":json.dumps({"content":"Should not save","keep_ids":[foreign["id"]]})})
        self.assertEqual(invalid.status_code,404)
        self.assertEqual(self.a.get("/api/v1/my/profile").json()["posts"][0]["content"],"Edited")
        self.assertEqual(self.a.delete(f"/api/v1/my/posts/{post['id']}").status_code,204)
        self.assertEqual(self.a.get(two["url"]).status_code,404)
        self.assertEqual(self.a.get("/api/v1/my/profile").json()["pins"],[])

    def test_limits_and_invalid_payloads_do_not_leave_partial_posts(self):
        with patch("app.routers.feed.MAX_FILE_SIZE",4):
            self.assertEqual(self.upload(content=b"12345").status_code,413)
        with patch("app.routers.feed.MAX_POST_SIZE",5):
            response = self.a.post("/api/v1/my/feed",data={"payload":json.dumps({"content":"Too much"})},files=[("files",("one",b"123")),("files",("two",b"456"))])
            self.assertEqual(response.status_code,413,response.text)
        for payload in [{},{"url":"javascript:alert(1)"},{"content":"test","keep_ids":[1,1]}]:
            response = self.a.post("/api/v1/my/feed",data={"payload":json.dumps(payload)})
            self.assertEqual(response.status_code,422,response.text)
        self.assertEqual(self.a.get("/api/v1/my/profile").json()["posts"],[])
        self.assertEqual(self.a.get("/api/v1/my/files").json(),[])

    def test_unpinning_keeps_file_in_owner_library_and_preserves_download(self):
        item = self.upload("empty.txt",b"").json()
        self.assertEqual(self.a.put(f"/api/v1/my/files/{item['id']}",json={"pinned":False}).status_code,200)
        self.assertEqual(self.a.get("/api/v1/my/profile").json()["pins"],[])
        self.assertEqual(self.a.get("/api/v1/my/files").json()[0]["id"],item["id"])
        self.assertEqual(self.a.get(item["url"]).status_code,200)
        self.assertEqual(self.a.get(item["url"]).content,b"")

    def test_edit_can_replace_pinned_files_at_capacity_without_exceeding_ten(self):
        post=self.post(files=[("files",("one",b"1")),("files",("two",b"2"))],pin_new=True)
        for index in range(8):
            self.assertEqual(self.upload(f"standalone-{index}").status_code,201)
        response=self.a.put(f"/api/v1/my/feed/{post['id']}",data={"payload":json.dumps({"content":"Replacement","keep_ids":[post['attachments'][1]['id']],"pin_new":True})},files=[("files",("replacement",b"3"))])
        self.assertEqual(response.status_code,200,response.text)
        self.assertEqual(len(self.a.get("/api/v1/my/profile").json()["pins"]),10)
        self.assertEqual([f["name"] for f in response.json()["attachments"]],["two","replacement"])
