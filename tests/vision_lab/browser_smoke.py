"""Optional real Chromium/Qt fixture browser test; never touches a user's archives.
Install PySide6 separately. Run with QT_QPA_PLATFORM=offscreen on a headless host.
Root-only container testing may require QTWEBENGINE_DISABLE_SANDBOX=1; never set
that for an ordinary user's browser or the Vision Lab application.
"""
import os
import json
import tempfile
import threading
from pathlib import Path
from http.server import ThreadingHTTPServer
from PySide6.QtWidgets import QApplication
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtCore import QUrl,QTimer
from vision_lab.demo import create
from vision_lab.server import application

script=r"""
(async()=>{
 const sleep=ms=>new Promise(r=>setTimeout(r,ms));
 for(let n=0;n<100&&!document.querySelector('.frame button');n++)await sleep(100);
 const buttons=[...document.querySelectorAll('.frame button')];
 if(buttons.length!==8)throw Error('Expected 8 synthetic fixture frames');
 document.getElementById('reviewer').value='Synthetic browser regression tester';
 buttons.find(b=>!b.textContent.includes('HELD OUT')).click();
 for(let n=0;n<100&&(!document.getElementById('loading').hidden);n++)await sleep(100);
 if(!document.getElementById('loading').hidden)throw Error('Image never decoded');
 const canvas=document.getElementById('canvas'),r=canvas.getBoundingClientRect(),scale=Math.min(r.width/96,r.height/96)*.95;
 const ox=(r.width-96*scale)/2,oy=(r.height-96*scale)/2;
 // Fixture events exercise production editor handlers; capture needs a trusted
 // hardware pointer, so replace capture only in this isolated browser test.
 canvas.setPointerCapture=()=>{};
 const event=(x,y)=>({clientX:r.left+ox+x*scale,clientY:r.top+oy+y*scale,pointerId:1,button:0,shiftKey:false});
 const drag=(x,y,a,b)=>{canvas.onpointerdown(event(x,y));canvas.onpointermove(event(a,b));canvas.onpointerup(event(a,b))};
 drag(40,40,55,50);
 const count=()=>document.querySelectorAll('#objects button').length;
 if(count()!==3)throw Error('Drawing failed');
 document.getElementById('undo').click();if(count()!==2)throw Error('Undo failed');
 document.getElementById('redo').click();if(count()!==3)throw Error('Redo failed');
 document.querySelectorAll('#objects button')[2].click();drag(47,45,49,46); // move
 drag(57,51,59,53); // resize selected lower-right corner
 document.getElementById('zoomIn').click();document.getElementById('fit').click();
 document.getElementById('saveDraft').click();
 for(let n=0;n<100&&!document.getElementById('notice').textContent.includes('Saved revision 2');n++)await sleep(100);
 if(!document.getElementById('notice').textContent.includes('Saved revision 2'))throw Error('Save not acknowledged');
 document.querySelector('#tabs button[data-tab="sources"]').click();
 if(!document.getElementById('sources').classList.contains('active'))throw Error('Sources tab failed');
 document.querySelector('#tabs button[data-tab="workspace"]').click();
 window.__result={ok:true,frames:8,boxes:count(),notice:document.getElementById('notice').textContent};
})().catch(e=>window.__result={ok:false,error:String(e)})
"""

def main():
    app=QApplication([]);view=QWebEngineView();view.resize(1280,1100);view.show();result=[]
    with tempfile.TemporaryDirectory(prefix='vision-browser-SYNTHETIC-') as tmp:
        lab,_=create(Path(tmp)/'fixture');server=ThreadingHTTPServer(('127.0.0.1',0),application(lab,None,'fixture-browser-token',0))
        port=server.server_port;server.RequestHandlerClass=application(lab,None,'fixture-browser-token',port)
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        def poll():
            def received(raw):
                if not raw:return
                value=json.loads(raw);result.append(value)
                if value.get('ok'):
                    rows=[lab.annotation(f['id']) for f in lab.frames()];changed=[a for a in rows if a['revision']==2]
                    value['history_verified']=len(changed)==1 and len(changed[0]['boxes'])==3 and changed[0]['status']=='draft' and len(lab.history(changed[0]['frame_id']))==2
                    b=changed[0]['boxes'][-1];value['move_resize_verified']=abs(b['x']-42)<.1 and abs(b['y']-41)<.1 and abs(b['w']-17)<.1 and abs(b['h']-12)<.1
                    value['ok']=value['history_verified'] and value['move_resize_verified']
                if os.environ.get('VISION_LAB_BROWSER_SCREENSHOT'):view.grab().save(os.environ['VISION_LAB_BROWSER_SCREENSHOT'])
                print(json.dumps(value),flush=True);app.quit()
            view.page().runJavaScript("window.__result ? JSON.stringify(window.__result) : ''",received)
        view.loadFinished.connect(lambda ok:view.page().runJavaScript(script) if ok else None)
        timer=QTimer();timer.timeout.connect(poll);timer.start(250);QTimer.singleShot(30000,app.quit)
        view.setUrl(QUrl(f'http://127.0.0.1:{port}'));app.exec();server.shutdown();thread.join();server.server_close()
    if not result:raise SystemExit('Browser fixture timed out')
    if not result[-1].get('ok'):raise SystemExit(1)

if __name__=='__main__':main()
