"""Live validation of network interception via the chromium-bidi mapper (driverless)."""
import functools, http.server, socketserver, sys, tempfile, threading, time, traceback
from pathlib import Path
import os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from bidi_core.launcher import launch_chromium_driverless
from bidi_core.manager import BiDiManager

# fixture dir
d = Path(tempfile.mkdtemp()); (d/"api").mkdir()
(d/"index.html").write_text("""<!doctype html><title>Intercept</title><script>
window.__ready=(async()=>{
 try{const r=await fetch('/api/data.json');window.__data=await r.json();}catch(e){window.__dataErr=String(e);}
 try{const r=await fetch('/api/flaky.json');window.__flaky=await r.json();}catch(e){window.__flakyErr=String(e);}
})();</script>""")
(d/"api"/"data.json").write_text('{"userId": 42}')   # REAL value (mock overrides to 999)
(d/"api"/"flaky.json").write_text('{"x": 1}')
class H(http.server.SimpleHTTPRequestHandler):
    def log_message(self,*a): pass
httpd = socketserver.TCPServer(("127.0.0.1",0), functools.partial(H, directory=str(d)))
threading.Thread(target=httpd.serve_forever, daemon=True).start()
base = f"http://127.0.0.1:{httpd.server_address[1]}/"

results=[]
def check(n,c,detail=""):
    results.append(bool(c)); print(f"[{'PASS' if c else 'FAIL'}] {n}"+(f" :: {detail}" if detail else ""),flush=True)

def main():
    b = launch_chromium_driverless(headless=True, extra_args=["--no-sandbox","--disable-dev-shm-usage"])
    m = BiDiManager()
    try:
        m.connect(b.bidi_url, browser="chromium", transport="cdp-mapper",
                  auto_subscribe=["network.responseCompleted"])
        ctx = m._loop.run(m._commands.browsing_context.get_tree(), timeout=10)["contexts"][0]["context"]
        # Register intercepts BEFORE navigation
        m.add_mock("*/api/data.json", status=200, body='{"userId": 999}',
                   headers={"content-type": "application/json"})
        m.add_fault("*/api/flaky.json")
        m._loop.run(m._client.send_command("browsingContext.navigate",
            {"context": ctx, "url": base+"index.html", "wait": "complete"}), timeout=30)
        time.sleep(2)
        data = m.evaluate("window.__data && window.__data.userId", context=ctx)
        check("mock overrides response body (userId 999)", data == 999, f"got {data}")
        flaky_err = m.evaluate("window.__flakyErr || null", context=ctx)
        check("fault injection makes fetch fail", bool(flaky_err), f"err={flaky_err}")
        ttfb = m.get_response_timing("*index.html*", "ttfb")
        check("TTFB timing is a number", isinstance(ttfb, (int, float)), f"ttfb={ttfb}ms")
        m.clear_intercepts()
        check("clear intercepts", not m._actions)
        m.disconnect()
    except Exception:
        print("ERROR:\n"+traceback.format_exc(), flush=True)
    finally:
        httpd.shutdown(); b.close()
    print(f"\n{sum(results)}/{len(results)} checks passed", flush=True)
    return 0 if results and sum(results)==len(results) else 1

if __name__=="__main__":
    raise SystemExit(main())
