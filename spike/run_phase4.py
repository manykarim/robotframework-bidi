"""Live validation: uploads, wheel scroll, cookie seeding, navigation events, downloads."""
import functools, http.server, socketserver, sys, tempfile, threading, time, traceback
from pathlib import Path
import os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from bidi_core.launcher import launch_chromium_driverless
from bidi_core.manager import BiDiManager
from bidi_core.bidi_client import BiDiError

d = Path(tempfile.mkdtemp())
(d/"page.html").write_text("""<!doctype html><title>P4</title>
<style>body{height:4000px;margin:0}</style>
<input id="upload" type="file" style="position:absolute;left:-9999px">
<button id="spa" onclick="history.pushState({},'','/route2')">go</button>
""")
up = Path(tempfile.mkdtemp())/"file.txt"; up.write_text("hello upload")
class H(http.server.SimpleHTTPRequestHandler):
    def log_message(self,*a): pass
httpd = socketserver.TCPServer(("127.0.0.1",0), functools.partial(H, directory=str(d)))
threading.Thread(target=httpd.serve_forever, daemon=True).start()
port = httpd.server_address[1]; base=f"http://127.0.0.1:{port}/"

results=[]
def check(n,c,detail=""):
    results.append(bool(c)); print(f"[{'PASS' if c else 'FAIL'}] {n}"+(f" :: {detail}" if detail else ""),flush=True)
def nav(m,ctx,url): m._loop.run(m._client.send_command("browsingContext.navigate",
    {"context":ctx,"url":url,"wait":"complete"}), timeout=30)

def main():
    b=launch_chromium_driverless(headless=True, extra_args=["--no-sandbox","--disable-dev-shm-usage"])
    m=BiDiManager()
    try:
        m.connect(b.bidi_url, browser="chromium", transport="cdp-mapper",
                  auto_subscribe=["browsingContext.historyUpdated","browsingContext.load"])
        ctx=m._loop.run(m._commands.browsing_context.get_tree(),timeout=10)["contexts"][0]["context"]

        # cookie seed BEFORE navigation
        m.set_cookie("auth", "tok123", "127.0.0.1", http_only=False)
        nav(m,ctx,base+"page.html")
        cookie=m.evaluate("document.cookie", context=ctx)
        check("cookie seeding visible to page", "auth=tok123" in (cookie or ""), repr(cookie))

        # file upload to hidden input
        m.set_files("css", "#upload", [str(up)], context=ctx)
        nfiles=m.evaluate("document.querySelector('#upload').files.length", context=ctx)
        check("setFiles on hidden input", nfiles==1, f"files={nfiles}")

        # wheel scroll
        m.wheel_scroll(0, 800, x=50, y=50, context=ctx)
        time.sleep(0.3)
        sy=m.evaluate("window.scrollY", context=ctx)
        check("wheel scroll moved page", (sy or 0) > 0, f"scrollY={sy}")

        # SPA navigation event (historyUpdated)
        m.clear_buffers()
        m.evaluate("document.getElementById('spa').click()", context=ctx)
        evt=m.wait_for_navigation("historyUpdated", context=ctx, timeout=5)
        check("SPA historyUpdated captured", "route2" in (evt.get("url","")), evt.get("url"))

        # downloads (probe)
        try:
            m.set_download_behavior(destination_folder="/tmp/dl")
            check("set_download_behavior accepted", True)
        except BiDiError as e:
            print(f"[SKIP] downloads unsupported :: {str(e)[:70]}",flush=True)

        m.disconnect()
    except Exception:
        print("ERROR:\n"+traceback.format_exc(),flush=True)
    finally:
        httpd.shutdown(); b.close()
    print(f"\n{sum(results)}/{len(results)} hard checks passed",flush=True)
    return 0 if results and sum(results)==len(results) else 1
if __name__=="__main__": raise SystemExit(main())
