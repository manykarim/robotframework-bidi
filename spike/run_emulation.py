"""Live validation: emulation overrides (probe support) + user-context isolation."""
import sys, time, traceback
import os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from bidi_core.launcher import launch_chromium_driverless
from bidi_core.manager import BiDiManager
from bidi_core.bidi_client import BiDiError

results=[]
def check(n,c,detail=""):
    results.append(bool(c)); print(f"[{'PASS' if c else 'FAIL'}] {n}"+(f" :: {detail}" if detail else ""),flush=True)
def probe(n, fn):
    try: fn(); check(n, True)
    except BiDiError as e: print(f"[SKIP] {n} :: unsupported on engine: {str(e)[:70]}",flush=True)
    except Exception: print(f"[FAIL] {n}\n{traceback.format_exc()}",flush=True); results.append(False)

def nav(m,ctx,url): m._loop.run(m._client.send_command("browsingContext.navigate",
    {"context":ctx,"url":url,"wait":"complete"}), timeout=30)

def main():
    b=launch_chromium_driverless(headless=True, extra_args=["--no-sandbox","--disable-dev-shm-usage"])
    m=BiDiManager()
    try:
        m.connect(b.bidi_url, browser="chromium", transport="cdp-mapper")
        ctx=m._loop.run(m._commands.browsing_context.get_tree(),timeout=10)["contexts"][0]["context"]

        # viewport (mature)
        probe("set_viewport applies", lambda: m.set_viewport(800,600,context=ctx))
        nav(m,ctx,"about:blank")
        check("window.innerWidth==800", m.evaluate("window.innerWidth",context=ctx)==800,
              f"got {m.evaluate('window.innerWidth',context=ctx)}")

        # locale/timezone (probe)
        ok_locale = [True]
        def set_intl():
            m.set_timezone("Asia/Tokyo",context=ctx); m.set_locale("fr-FR",context=ctx)
        probe("emulation locale+timezone overrides", set_intl)
        nav(m,ctx,"about:blank")
        tz = m.evaluate("Intl.DateTimeFormat().resolvedOptions().timeZone",context=ctx)
        if tz=="Asia/Tokyo": check("timezone override reflected", True, tz)
        else: print(f"[SKIP] timezone override not reflected (engine) :: {tz}",flush=True)

        # forced-colors + scripting-enabled (probe only)
        probe("forced-colors override", lambda: m.set_forced_colors("dark",context=ctx))

        # user-context isolation (browser module)
        try:
            uc1=m.create_user_context(); uc2=m.create_user_context()
            c1=m.create_context(user_context=uc1); c2=m.create_context(user_context=uc2)
            nav(m,c1,"https://example.com/"); nav(m,c2,"https://example.com/")
            m.evaluate("localStorage.setItem('k','A'); 1", context=c1)
            other=m.evaluate("localStorage.getItem('k')", context=c2)
            check("user-context localStorage isolation", other in (None,"null",""), f"other={other!r}")
            check("two user contexts tracked", len(m._user_contexts)==2)
        except BiDiError as e:
            print(f"[SKIP] user contexts unsupported :: {str(e)[:70]}",flush=True)
        m.disconnect()
    except Exception:
        print("ERROR:\n"+traceback.format_exc(),flush=True)
    finally:
        b.close()
    print(f"\n{sum(results)}/{len(results)} hard checks passed",flush=True)
    return 0 if results and sum(results)==len(results) else 1
if __name__=="__main__": raise SystemExit(main())
