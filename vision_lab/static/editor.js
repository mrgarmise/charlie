export function rect(a,b,width,height){const x=Math.max(0,Math.min(width,Math.min(a.x,b.x))),y=Math.max(0,Math.min(height,Math.min(a.y,b.y)));return {x,y,w:Math.max(0,Math.min(width,Math.max(a.x,b.x))-x),h:Math.max(0,Math.min(height,Math.max(a.y,b.y))-y)}}
export function moveBox(b,dx,dy,width,height){return {...b,x:Math.max(0,Math.min(width-b.w,b.x+dx)),y:Math.max(0,Math.min(height-b.h,b.y+dy))}}
export class Editor{
 constructor(canvas,changed){this.canvas=canvas;this.ctx=canvas.getContext('2d');this.changed=changed;this.boxes=[];this.selected=-1;this.undoStack=[];this.redoStack=[];this.scale=1;this.offset={x:0,y:0};this.drawMode=true;this.label='player';this.space=false;this.loaded=false;this.dirty=false;
 canvas.oncontextmenu=e=>e.preventDefault();canvas.onpointerdown=e=>this.down(e);canvas.onpointermove=e=>this.drag(e);canvas.onpointerup=e=>this.up(e);canvas.onpointercancel=e=>this.up(e);
 canvas.addEventListener('wheel',e=>{e.preventDefault();this.zoom(e.deltaY<0?1.12:1/1.12,this.screen(e))},{passive:false});
 window.addEventListener('resize',()=>this.paint());window.addEventListener('keydown',e=>{if(e.target.matches('input,textarea,select'))return;if(e.code==='Space'){e.preventDefault();this.space=true}});window.addEventListener('keyup',()=>this.space=false);window.addEventListener('blur',()=>this.space=false);
 }
 snapshot(){this.undoStack.push(structuredClone(this.boxes));this.undoStack=this.undoStack.slice(-100);this.redoStack=[]}
 update(){this.dirty=true;this.paint();this.changed()}
 set(image,boxes){this.image=image;this.boxes=structuredClone(boxes);this.selected=-1;this.undoStack=[];this.redoStack=[];this.loaded=true;this.dirty=false;this.fit();this.changed()}
 clear(){this.image=null;this.loaded=false;this.boxes=[];this.paint()}
 screen(e){const r=this.canvas.getBoundingClientRect();return {x:e.clientX-r.left,y:e.clientY-r.top}}
 world(e){const p=this.screen(e);return {x:(p.x-this.offset.x)/this.scale,y:(p.y-this.offset.y)/this.scale}}
 fit(){if(!this.image)return;const r=this.canvas.getBoundingClientRect();this.scale=Math.min(r.width/this.image.width,r.height/this.image.height)*.95;this.offset={x:(r.width-this.image.width*this.scale)/2,y:(r.height-this.image.height*this.scale)/2};this.paint()}
 zoom(factor,p){if(!this.image)return;const r=this.canvas.getBoundingClientRect();p=p||{x:r.width/2,y:r.height/2};const world={x:(p.x-this.offset.x)/this.scale,y:(p.y-this.offset.y)/this.scale};this.scale=Math.max(.05,Math.min(30,this.scale*factor));this.offset={x:p.x-world.x*this.scale,y:p.y-world.y*this.scale};this.paint()}
 down(e){if(!this.loaded)return;this.canvas.focus();this.canvas.setPointerCapture(e.pointerId);const p=this.world(e);this.start=p;this.original=null;
 if(this.space||e.button===2){this.mode='pan';this.startScreen=this.screen(e);this.originalOffset={...this.offset};return}
 const box=this.boxes[this.selected];if(box){const corners=[[box.x,box.y],[box.x+box.w,box.y],[box.x+box.w,box.y+box.h],[box.x,box.y+box.h]];const index=corners.findIndex(([x,y])=>Math.hypot(p.x-x,p.y-y)<9/this.scale);if(index>=0){this.mode='resize';this.anchor={x:corners[(index+2)%4][0],y:corners[(index+2)%4][1]};this.snapshot();return}}
 const hit=this.boxes.findLastIndex(b=>p.x>=b.x&&p.x<=b.x+b.w&&p.y>=b.y&&p.y<=b.y+b.h);
 if(hit>=0&&!e.shiftKey){this.selected=hit;this.mode='move';this.original={...this.boxes[hit]};this.snapshot();this.changed();return}
 this.mode='draw';this.snapshot();this.selected=this.boxes.length;this.boxes.push({...rect(p,p,this.image.width,this.image.height),class_name:this.label,confidence:1,uncertain:this.label==='unknown',accepted:false,origin:'human'});this.update();
 }
 drag(e){if(!this.mode)return;const p=this.world(e);
 if(this.mode==='pan'){const s=this.screen(e);this.offset={x:this.originalOffset.x+s.x-this.startScreen.x,y:this.originalOffset.y+s.y-this.startScreen.y};this.paint();return}
 if(this.mode==='move')this.boxes[this.selected]=moveBox(this.original,p.x-this.start.x,p.y-this.start.y,this.image.width,this.image.height);
 else Object.assign(this.boxes[this.selected],rect(this.mode==='resize'?this.anchor:this.start,p,this.image.width,this.image.height));
 const b=this.boxes[this.selected];b.accepted=false;if(b.model_id)b.origin='model-corrected';this.update();
 }
 up(){if(this.mode==='draw'&&this.boxes[this.selected]&&(this.boxes[this.selected].w<2||this.boxes[this.selected].h<2)){this.boxes.splice(this.selected,1);this.selected=-1;this.update()}this.mode=null}
 change(fields){if(this.selected<0)return;this.snapshot();Object.assign(this.boxes[this.selected],fields,{accepted:false});if(this.boxes[this.selected].model_id)this.boxes[this.selected].origin='model-corrected';this.update()}
 remove(){if(this.selected<0)return;this.snapshot();this.boxes.splice(this.selected,1);this.selected=-1;this.update()}
 undo(){if(!this.undoStack.length)return;this.redoStack.push(structuredClone(this.boxes));this.boxes=this.undoStack.pop();this.selected=-1;this.update()}
 redo(){if(!this.redoStack.length)return;this.undoStack.push(structuredClone(this.boxes));this.boxes=this.redoStack.pop();this.selected=-1;this.update()}
 paint(){const r=this.canvas.getBoundingClientRect(),dpr=window.devicePixelRatio||1;this.canvas.width=r.width*dpr;this.canvas.height=r.height*dpr;const c=this.ctx;c.setTransform(dpr,0,0,dpr,0,0);c.clearRect(0,0,r.width,r.height);if(!this.image)return;c.save();c.translate(this.offset.x,this.offset.y);c.scale(this.scale,this.scale);c.drawImage(this.image,0,0);
 this.boxes.forEach((b,i)=>{c.strokeStyle=b.uncertain?'#ffb95c':i===this.selected?'#00ffbb':'#65adff';c.lineWidth=2/this.scale;c.strokeRect(b.x,b.y,b.w,b.h);c.fillStyle=c.strokeStyle;c.font=`${13/this.scale}px system-ui`;c.fillText(b.class_name,b.x,Math.max(14/this.scale,b.y-4/this.scale));if(i===this.selected){for(const [x,y] of [[b.x,b.y],[b.x+b.w,b.y],[b.x+b.w,b.y+b.h],[b.x,b.y+b.h]])c.fillRect(x-4/this.scale,y-4/this.scale,8/this.scale,8/this.scale)}});c.restore()}
}
