import os, threading, http.server, pytest

FORM = """<!doctype html><html><head><title>Job Application for Research Intern at MockCo</title></head><body>
<h1>Research Intern</h1>
<form id="f" onsubmit="return go(event)">
<label for="first_name">First Name*</label><input id="first_name" required aria-required="true"><br>
<label for="last_name">Last Name*</label><input id="last_name" required aria-required="true"><br>
<label for="email">Email*</label><input id="email" required aria-required="true"><br>
<label for="phone">Phone</label><input id="phone" type="tel"><br>
<label for="resume">Resume*</label><input id="resume" name="resume" type="file" required><br>
<label for="auth">Are you legally authorized to work in the US?*</label>
<select id="auth" required><option value="">Select...</option><option>Yes</option><option>No</option></select><br>
<label id="lbl_cb">Have you ever worked at MockCo before?*</label>
<div class="field"><div class="select__control"><div class="value">Select...</div>
<div><input id="cb" role="combobox" aria-controls="lb" aria-labelledby="lbl_cb" aria-required="true"></div></div>
<ul id="lb" role="listbox" hidden><li role="option">Yes</li><li role="option">No</li></ul></div>
%(extra)s
<button type="submit">Submit application</button></form>
<script>
const cb=document.getElementById('cb'),lb=document.getElementById('lb');
cb.addEventListener('click',()=>lb.hidden=false);cb.addEventListener('input',()=>lb.hidden=false);
lb.querySelectorAll('li').forEach(li=>li.addEventListener('click',()=>{
  document.querySelector('.select__control .value').textContent=li.textContent;cb.value='';lb.hidden=true;}));
async function go(e){e.preventDefault();
  if(document.querySelector('.value').textContent.startsWith('Select')){return false}
  await fetch('/submit',{method:'POST',body:'x'});document.body.innerHTML='<h1>Thank you for applying!</h1>';return false}
</script></body></html>"""

EXTRAS = {
    "basic": "",
    "essay": '<label for="why">Why do you want to join MockCo?*</label><textarea id="why" required aria-required="true"></textarea>',
    "captcha": '<iframe src="about:blank#recaptcha" width="10" height="10"></iframe>',
    "unknown": '<label for="x">What is your favourite obscure thing?*</label><input id="x" required aria-required="true">',
}


@pytest.fixture(scope="session")
def mock_site():
    posts = []

    class H(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            key = self.path.strip("/").split("?")[0] or "basic"
            body = (FORM % {"extra": EXTRAS.get(key, "")}).encode()
            self.send_response(200); self.send_header("Content-Type", "text/html"); self.end_headers()
            self.wfile.write(body)

        def do_POST(self):
            self.rfile.read(int(self.headers.get("Content-Length", 0)))
            posts.append(self.path); self.send_response(200); self.end_headers()

        def log_message(self, *a):
            pass

    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_address[1]}", posts
    srv.shutdown()


@pytest.fixture(scope="session")
def browser():
    pw = pytest.importorskip("playwright.sync_api")
    with pw.sync_playwright() as p:
        exe = os.environ.get("CHROMIUM_PATH")
        b = p.chromium.launch(args=["--no-sandbox"], **({"executable_path": exe} if exe else {}))
        yield b
        b.close()


@pytest.fixture
def profile(tmp_path):
    resume = tmp_path / "resume.pdf"
    resume.write_bytes(b"%PDF-1.4 test")
    return {"first_name": "Test", "last_name": "User", "email": "t@example.com", "phone": "555",
            "resume": str(resume), "background": "A student.",
            "answers": {"authorized to work": "Yes", "worked at .* before": "No"}, "apply": {}}
