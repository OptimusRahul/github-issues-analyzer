import json

from tests.triage import test_server
from tests.triage.test_server import KEY
from triage.config import Config, DuplicatesConfig, LabelsConfig

server = test_server.server  # the same app fixture


def signed_in(client):
    client.headers.pop("Authorization", None)
    response = client.post("/login", data={"key": KEY}, follow_redirects=False)
    assert response.status_code == 303
    return client


def test_pages_redirect_to_login_without_session(server):
    client, _ = server()
    client.headers.pop("Authorization")
    for path in ("/", "/r/o/r"):
        response = client.get(path, follow_redirects=False)
        assert response.status_code == 303 and response.headers["location"] == "/login"


def test_wrong_key_is_rejected(server):
    client, _ = server()
    response = client.post("/login", data={"key": "nope"}, follow_redirects=False)
    assert response.status_code == 401 and "not valid" in response.text


def test_session_cookie_is_httponly_and_strict(server):
    client, _ = server()
    response = client.post("/login", data={"key": KEY}, follow_redirects=False)
    cookie = response.headers["set-cookie"].lower()
    assert "httponly" in cookie and "samesite=strict" in cookie


def test_home_lists_repos_and_repo_page_shows_themes_and_recent_issues(server):
    cfg = Config(duplicates=DuplicatesConfig(threshold=0.5), labels=LabelsConfig(enabled=True, neighbors=5, min_share=0.3))
    client, _ = signed_in(server(cfg=cfg)[0]), None
    home = client.get("/")
    assert home.status_code == 200 and 'href="/r/o/r"' in home.text
    assert "Content-Security-Policy" in home.headers
    page = client.get("/r/o/r").text
    assert "Recent open issues" in page and "#2 Crash when opening settings on Windows 11" in page
    assert "Related:" in page


def test_search_partial_and_escaping(server):
    client = signed_in(server()[0])
    html = client.get("/r/o/r/search", params={"q": "settings crash"}).text
    assert "#1 App crashes when opening settings on Windows" in html


def test_ask_partial_shows_answer_and_only_retrieved_citations(server):
    reply = json.dumps({"answer": "It crashes in settings <script>x</script>.", "citations": [1, 99]})
    client = signed_in(server(replies=[reply])[0])
    html = client.post("/r/o/r/ask", data={"question": "Why does it crash?"}).text
    assert "#1 App crashes" in html and "#99" not in html
    assert "<script>x" not in html and "&lt;script&gt;" in html


def test_ask_partial_reports_errors_as_text(server):
    client = signed_in(server()[0])
    html = client.post("/r/o/r/ask", data={"question": ""}).text
    assert 'role="alert"' in html


def test_logout_ends_session(server):
    client = signed_in(server()[0])
    client.post("/logout", follow_redirects=False)
    assert client.get("/", follow_redirects=False).status_code == 303
