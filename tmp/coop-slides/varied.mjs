import fs from 'node:fs/promises';
import path from 'node:path';
import {pathToFileURL} from 'node:url';
import {Presentation,PresentationFile} from 'file:///C:/Users/avuil/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/@oai/artifact-tool/dist/artifact_tool.mjs';
const root='C:/Users/avuil/Desktop/Therapist-Dashboard-Software';
const build=root+'/tmp/coop-slides';
const skill='C:/Users/avuil/.codex/plugins/cache/openai-primary-runtime/presentations/26.1015.12040/skills/presentations';
const p=Presentation.create({slideSize:{width:1280,height:720}});
function text(s,txt,x,y,w,h,size=28,color='#29443E',bold=false){const a=s.shapes.add({geometry:'textbox',position:{left:x,top:y,width:w,height:h},fill:'none',line:{fill:'none',width:0}});a.text=txt;a.text.style={fontFamily:'Aptos',fontSize:size,color,bold};return a;}
function slide(title,subtitle,rows,notes){
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
   rows.forEach((r,i)=>{const x=80+i*390;label(r[0],x,286,345,70,30);body(r[1],x,372,300,220,26);});
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
}
slide('Therapist Dashboard','Solo co-op project / Proof-of-concept demo',[
 ['Purpose','A workspace to help therapists organize session information and reduce administrative effort.'],
 ['Agenda','Project goals, accomplishments so far, current hurdles, and the end-of-co-op plan.'],
 ['Demo scope','A working core session flow, with UI fixtures showing the wider product experience.']
], 'The presenter is the sole project contributor. The user describes the intended co-op outcome as a demo proof of concept with as many UI fixtures as possible, even where functionality is incomplete. Sources: README.md; docs/product/PROJECT_VISION.md, sections 1, 2 and 7. Core implementation exists in frontend/src/components/session-review/. This deck reports code and documented direction, not a fresh end-to-end test.');
slide('Project purpose and goals','Primary audience: therapists. Longer-term audience: clients and clinical teams.',[
 ['Session review','Bring recordings, timestamped transcripts, and draft clinical notes into one workflow.'],
 ['Continuity of care','Make past-session context easier to revisit, with links to supporting records.'],
 ['Therapist control','Keep generated material reviewable and correctable before clinical use.']
], 'Sources: docs/product/PROJECT_VISION.md, sections 1–7; docs/ai/AI_ML_VISION.md, sections 1–4. These are intended benefits, not measured outcomes. AI assists clinicians and does not replace clinical judgment.');
slide('Accomplishments so far','The codebase contains the core session workflow and a broader interface foundation.',[
 ['Capture and process','Browser recording and audio uploads connect to HealthScribe for transcripts and draft notes.'],
 ['Review and correct','Transcript-linked playback, speaker-label corrections, and note editing and finalization.'],
 ['Broader UI coverage','Client records, scheduling, Insights, a client portal, and settings screens.']
], 'Sources: README.md; docs/ai/HEALTHSCRIBE.md, Purpose and What the local application does today; frontend/src/components/session-review/recording-controls.tsx; audio-upload-button.tsx; transcript-viewer.tsx (segment selection sets player.currentTime); speaker-label-editor.tsx; clinical-note.tsx (save and finalize API calls). Broader interface sources: frontend/src/components/client-list.tsx; therapist-calendar.tsx; client-insights.tsx; client-portal.tsx; settings-layout.tsx. UI presence does not establish complete backend functionality or production readiness.');
slide('Progress against the demo goal','The repository supports a substantial proof of concept. Full demo coverage remains the target.',[
 ['Goal','Show the intended therapist experience through a core workflow and broad UI fixtures.'],
 ['Progress','Core review controls and multiple workspace screens are present in the codebase.'],
 ['Remaining gap','Check the full demo path and clearly identify which interactions use fixtures.']
], 'The user supplied the goal: a demo proof-of-concept version with as many UI fixtures in place as possible, not necessarily functional. No original milestone schedule or signed acceptance criteria were provided, so this deck does not claim every committed goal is complete. Code references: frontend/src/components/session-review/session-workspace.tsx; scheduled-session-layout.tsx; completed-session-layout.tsx; frontend/src/app/clients/[clientId]/page.tsx. docs/deployment/HOSTED_DEPLOYMENT_ARCHITECTURE.md identifies a stable synthetic-data vertical slice as the readiness goal.');
slide('Current hurdles and future plans','Proposed end-of-co-op deliverable: a coherent demo using synthetic data.',[
 ['Demo reliability','Verify the full session path and make processing, loading, and error states clear.'],
 ['UI completeness','Fill priority screen gaps and keep fixture-based interactions consistent across the demo.'],
 ['Final handoff','Prepare a repeatable walkthrough and document implemented features, fixtures, and known limits.']
], 'This is a proposed delivery plan aligned with the user’s stated proof-of-concept scope, not an approved deadline commitment. Sources: docs/deployment/HOSTED_DEPLOYMENT_ARCHITECTURE.md, Product-readiness gate, especially core therapist session loop, Insights information architecture, reproducible startup and smoke checks; docs/product/PROJECT_VISION.md, strategic priorities. The documented readiness items are validation priorities, not a claim that every listed area is currently broken. Demo uses synthetic data. Real clinical deployment is outside this presentation’s completion claim.');
for(let i=0;i<p.slides.items.length;i++){const b=await p.export({slide:p.slides.items[i],format:'png',scale:1});await fs.writeFile(build+`/slide-${i+1}.png`,new Uint8Array(await b.arrayBuffer()));}
const candidate=build+'/candidate.pptx';await(await PresentationFile.exportPptx(p)).save(candidate);
const {finalizePresentation}=await import(pathToFileURL(skill+'/container_tools/artifact_tool_utils.mjs'));
const r=await finalizePresentation({workspaceDir:root,candidatePath:candidate,finalPath:root+'/output/coop-presentation/Therapist-Dashboard-Coop-Varied.pptx',pythonExecutable:'C:/Users/avuil/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe',integrityValidatorPath:skill+'/container_tools/inspect_presentation_package_integrity.py',layoutValidatorPath:skill+'/container_tools/inspect_presentation_layout_geometry.py',layoutArgs:['--expected-slide-size-emu','12192000,6858000','--validate-heading-fit'],fontPolicy:{basis:'design',families:['Aptos']},verifyArtifactToolImport:true,receiptPath:build+'/validation.json'});console.log(JSON.stringify(r));



