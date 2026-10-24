import io
import zipfile

from PIL import Image

from app.clients.llm_client import apply_free_text, collect_free_text, is_safe_correction
from app.schemas import Profile

PROFILE = {
    "basics": {"full_name": "Ada Lovelace", "headline": "Engineer"},
    "summary": "Builds analytical engines.",
    "experience": [{"company": "Babbage & Co", "title": "Programmer", "bullets": ["Wrote note G"]}],
    "skills": ["Math"],
    "links": [{"label": "Evil", "url": "javascript:alert(1)"}, {"label": "Site", "url": "ada.dev"}],
}


# ---------- auth ----------

def test_signup_login_refresh(client):
    r = client.post("/auth/signup", json={"email": "Bob@Example.com", "password": "password123"})
    assert r.status_code == 201 and r.json()["email"] == "bob@example.com"
    assert client.post("/auth/signup", json={"email": "bob@example.com", "password": "password123"}).status_code == 409
    assert client.post("/auth/login", json={"email": "bob@example.com", "password": "wrong-pass"}).status_code == 401

    tokens = client.post("/auth/login", json={"email": "bob@example.com", "password": "password123"}).json()
    assert client.get("/auth/me", headers={"Authorization": f"Bearer {tokens['access_token']}"}).status_code == 200
    # a refresh token must not work as an access token
    assert client.get("/auth/me", headers={"Authorization": f"Bearer {tokens['refresh_token']}"}).status_code == 401
    assert client.post("/auth/refresh", json={"refresh_token": tokens["refresh_token"]}).status_code == 200


def test_resume_requires_auth(client):
    assert client.get("/resume").status_code == 401


# ---------- resume CRUD ----------

def test_upsert_is_one_per_user(client, auth_headers):
    assert client.get("/resume", headers=auth_headers).status_code == 404
    first = client.put("/resume", json={"profile": PROFILE}, headers=auth_headers).json()
    second = client.put("/resume", json={"profile": {**PROFILE, "summary": "Changed"}},
                        headers=auth_headers).json()
    assert first["id"] == second["id"] and first["slug"] == second["slug"]
    assert second["profile"]["summary"] == "Changed"
    assert first["slug"].startswith("ada-lovelace-")


def test_correct_text_runs_after_save(client, auth_headers):
    body = {"profile": {**PROFILE, "summary": "first programer"}, "correct_text": True}
    assert client.put("/resume", json=body, headers=auth_headers).status_code == 200
    assert client.get("/resume", headers=auth_headers).json()["profile"]["summary"] == "first programmer"


# ---------- upload -> autofill ----------

def _docx_bytes() -> bytes:
    import docx

    d = docx.Document()
    d.add_paragraph("Ada Lovelace - ada@example.com - Mathematician and first programer. " * 3)
    buf = io.BytesIO()
    d.save(buf)
    return buf.getvalue()


def test_upload_parses_to_draft(client, auth_headers):
    files = {"file": ("cv.docx", _docx_bytes(), "application/octet-stream")}
    r = client.post("/resume/upload", files=files, headers=auth_headers)
    assert r.status_code == 202
    status = client.get(f"/resume/upload/{r.json()['id']}", headers=auth_headers).json()
    assert status["status"] == "done", status
    assert status["parsed_json"]["basics"]["full_name"] == "Ada Lovelace"
    assert status["parsed_json"]["summary"].endswith("first programmer.")
    # draft is not saved until the user confirms with PUT /resume
    assert client.get("/resume", headers=auth_headers).status_code == 404


def test_upload_rejects_spoofed_files(client, auth_headers):
    fake_pdf = {"file": ("cv.pdf", b"MZ\x90\x00 not a pdf", "application/pdf")}
    assert client.post("/resume/upload", files=fake_pdf, headers=auth_headers).status_code == 400
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("hello.txt", "hi")
    fake_docx = {"file": ("cv.docx", buf.getvalue(), "application/octet-stream")}
    assert client.post("/resume/upload", files=fake_docx, headers=auth_headers).status_code == 400
    mismatched = {"file": ("cv.pdf", _docx_bytes(), "application/pdf")}
    assert client.post("/resume/upload", files=mismatched, headers=auth_headers).status_code == 400


def test_upload_of_other_user_is_hidden(client, auth_headers):
    r = client.post("/resume/upload", files={"file": ("cv.docx", _docx_bytes(), "x")}, headers=auth_headers)
    client.post("/auth/signup", json={"email": "eve@example.com", "password": "password123"})
    t = client.post("/auth/login", json={"email": "eve@example.com", "password": "password123"}).json()
    eve = {"Authorization": f"Bearer {t['access_token']}"}
    assert client.get(f"/resume/upload/{r.json()['id']}", headers=eve).status_code == 404


# ---------- photo ----------

def _png(w=400, h=300) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (w, h), "red").save(buf, "PNG")
    return buf.getvalue()


def test_photo_upload_and_crop(client, auth_headers):
    r = client.post("/resume/photo", files={"file": ("me.png", _png(), "image/png")},
                    data={"crop_x": "50", "crop_y": "10", "crop_size": "200"}, headers=auth_headers)
    assert r.status_code == 200, r.text
    assert "/files/photos/" in r.json()["photo_url"]
    bad = client.post("/resume/photo", files={"file": ("me.png", _png(), "image/png")},
                      data={"crop_x": "300", "crop_y": "0", "crop_size": "200"}, headers=auth_headers)
    assert bad.status_code == 400
    not_image = client.post("/resume/photo", files={"file": ("me.png", b"%PDF-1.4", "image/png")},
                            headers=auth_headers)
    assert not_image.status_code == 400


# ---------- exports + public page ----------

def test_exports_and_public_page(client, auth_headers):
    assert client.post("/resume/export", json={"type": "ats"}, headers=auth_headers).status_code == 400
    client.put("/resume", json={"profile": PROFILE}, headers=auth_headers)

    ats = client.post("/resume/export", json={"type": "ats"}, headers=auth_headers)
    assert ats.status_code == 202
    job = client.get(f"/resume/export/{ats.json()['id']}", headers=auth_headers).json()
    assert job["status"] == "done" and job["output_url"].endswith(".pdf")

    cin = client.post("/resume/export", json={"type": "cinematic"}, headers=auth_headers).json()
    job = client.get(f"/resume/export/{cin['id']}", headers=auth_headers).json()
    assert job["status"] == "done" and "/r/" in job["public_url"]

    slug = job["public_url"].rsplit("/", 1)[1]
    page = client.get(f"/r/{slug}")
    assert page.status_code == 200
    assert "Ada Lovelace" in page.text and "Content-Security-Policy" in page.headers
    assert "javascript:alert" not in page.text  # unsafe link dropped
    assert 'href="https://ada.dev"' in page.text
    assert client.get("/resume", headers=auth_headers).json()["public_url"].endswith(slug)
    assert client.get("/r/does-not-exist").status_code == 404


# ---------- LLM guard helpers ----------

def test_correction_guard():
    assert is_safe_correction("I recieved teh award", "I received the award")
    assert not is_safe_correction("Led a team", "Led a team of 12 engineers to success")
    assert not is_safe_correction("Grew revenue", "Grew revenue 40%")


def test_free_text_roundtrip():
    p = Profile.model_validate(PROFILE)
    texts = collect_free_text(p)
    assert texts["exp.0.0"] == "Wrote note G"
    out = apply_free_text(p, {"exp.0.0": "Wrote Note G", "summary": "S"})
    assert out.experience[0].bullets[0] == "Wrote Note G" and out.summary == "S"
    assert p.summary == "Builds analytical engines."  # original untouched
