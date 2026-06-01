"""Driverless Chrome via chromium-bidi mapper — NO chromedriver."""
import sys, time, traceback
import os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from Browser_BiDi.launcher import launch_chromium_driverless
from Browser_BiDi.manager import BiDiManager

results=[]
def check(n,c,d=""):
    results.append(bool(c)); print(f"[{'PASS' if c else 'FAIL'}] {n}"+(f" :: {d}" if d else ""),flush=True)

def main():
    b = launch_chromium_driverless(headless=True, extra_args=["--no-sandbox","--disable-dev-shm-usage"])
    print("CDP/bidi url:", b.bidi_url, flush=True)
    m = BiDiManager(buffer_size=200)
    try:
        m.connect(b.bidi_url, browser="chromium", transport="cdp-mapper",
                  auto_subscribe=["network.responseCompleted","log.entryAdded"])
        check("connect via mapper (no chromedriver)", m.connected)
        check("data collector registered", m._collector is not None, str(m._collector))
        # Create a tab and navigate (BiDi through the mapper)
        ctx = m._loop.run(m._client.send_command("browsingContext.create",{"type":"tab"}), timeout=15)["context"]
        m._loop.run(m._client.send_command("browsingContext.navigate",
            {"context":ctx,"url":"https://example.com/","wait":"complete"}), timeout=30)
        time.sleep(1)
        check("title via BiDi", m.get_title(context=ctx) == "Example Domain", repr(m.get_title(context=ctx)))
        check("element count h1==1", m.get_element_count("css","h1",context=ctx) == 1)
        check("network responseCompleted captured", m.get_network_event_count(url_glob="*example.com*") >= 1)
        check("response status==200", m.get_response_status("*example.com*") == 200)
        # response body (headline capability) via mapper
        ev = m.get_network_events(url_glob="*example.com*")[0]
        rid = ev["request"]["request"]
        body = m.get_response_body(rid)
        check("response body retrieved", len(body) > 0, f"{len(body)} chars")
        m.disconnect()
    except Exception:
        print("ERROR:\n"+traceback.format_exc(),flush=True)
    finally:
        b.close()
    print(f"\n{sum(results)}/{len(results)} checks passed",flush=True)
    return 0 if results and sum(results)==len(results) else 1

if __name__=="__main__":
    raise SystemExit(main())
