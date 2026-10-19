from pathlib import Path
p=Path(__file__).with_name('build.mjs')
s=p.read_text(encoding='utf-8-sig')
start=s.index('function slide(')
end=s.index("\nslide('Therapist",start)
s=s[:start]+'''function slide(title,subtitle,rows,notes){
 const s=p.slides.add(), n=p.slides.items.length;
 s.background.fill='#F5F4EF';
 const heading=(x=76,y=65,w=1120,h=90,size=46)=>text(s,title,x,y,w,h,size,'#183E35',true);
 const label=(v,x,y,w=310,h=50,size=28)=>text(s,v,x,y,w,h,size,'#236B56',true);
 const body=(v,x,y,w,h=100,size=28)=>text(s,v,x,y,w,h,size);
 if(n===1){
   heading(76,102,470,160,58);
   text(s,subtitle,80,286,430,100,27,'#62746D');
   rows.forEach((r,i)=>{const y=105+i*175;label(r[0],610,y,560);body(r[1],610,y+49,560,115,27);});
 }else if(n===2){
   heading();text(s,subtitle,80,164,1100,66,25,'#62746D');
   rows.forEach((r,i)=>{const x=80+i*390;label(r[0],x,286,345,70,30);body(r[1],x,372,330,195,29);});
 }else if(n===3){
   heading();text(s,subtitle,80,164,1100,66,25,'#62746D');
   rows.forEach((r,i)=>{const y=263+i*108;label(r[0],80,y);body(r[1],420,y,770,88);});
 }else if(n===4){
   heading();text(s,subtitle,80,164,1100,75,25,'#62746D');
   label(rows[0][0],80,265,150);body(rows[0][1],260,262,900,100,32);
   rows.slice(1).forEach((r,i)=>{const x=80+i*610;label(r[0],x,423,500);body(r[1],x,482,495,140,28);});
 }else{
   heading(76,65,1120,95,44);
   text(s,subtitle,80,242,350,240,35,'#236B56',true);
   rows.forEach((r,i)=>{const y=232+i*133;label(String(i+1).padStart(2,'0'),510,y,60,45,25);label(r[0],605,y,565,45,28);body(r[1],605,y+45,565,90,26);});
 }
 text(s,String(n).padStart(2,'0'),1150,656,55,25,17,'#62746D');
 s.speakerNotes.text=notes;return s;
}'''+s[end:]
s=s.replace("finalPath:root+'/output/coop-presentation/Therapist-Dashboard-Coop.pptx'","finalPath:root+'/output/coop-presentation/Therapist-Dashboard-Coop-Varied.pptx'")
Path(__file__).with_name('varied.mjs').write_text(s,encoding='utf-8')
