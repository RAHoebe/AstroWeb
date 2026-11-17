// Syntax/translation/DOM-contract checks without a browser or build dependency.
import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';
import {fileURLToPath} from 'node:url';
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..','astroweb','static');
const files=['pinch.js','panorama.js','panorama-editor.js','footprint.js','collection.js','app.js','compare.js','polar.js','sky.js','atlas.js','i18n.js','guide.js','observatory.js','space-gl.js','distance-scenes.js'];
for(const file of files){
  const source=fs.readFileSync(path.join(root,file),'utf8');
  if(/[\u00c2\u00c3][^\x00-\x7f]|\ufffd/u.test(source))throw Error('Damaged UTF-8 text in '+file);
  new vm.SourceTextModule(source);
}
// Native TV packages also embed JavaScript and module scripts in HTML assets.
const tvRoot=path.resolve(root,'..','..','tv','app','src','main','assets');
let tvCount=0;
for(const file of fs.readdirSync(tvRoot)){
  const source=fs.readFileSync(path.join(tvRoot,file),'utf8');
  if(file.endsWith('.js')){new vm.Script(source,{filename:file});tvCount++;}
  if(file.endsWith('.html'))for(const match of source.matchAll(/<script([^>]*)>([\s\S]*?)<\/script>/g)){
    if(/type=["']module["']/.test(match[1]))new vm.SourceTextModule(match[2]);
    else new vm.Script(match[2],{filename:file});
    tvCount++;
  }
}
const i18n=fs.readFileSync(path.join(root,'i18n.js'),'utf8').replaceAll('export ','');
const context=vm.createContext({localStorage:{getItem:()=>null},document:{}});
vm.runInContext(i18n+';this.words=words;',context);
const html=['index.html','collection.html','guide.html','panorama.html','observatory.html'].map(f=>fs.readFileSync(path.join(root,f),'utf8')).join('\n');
const keys=[...html.matchAll(/data-i18n(?:-aria)?="([^"]+)"/g)].map(m=>m[1]);
for(const key of keys)if(!context.words[key])throw Error('Missing translation: '+key);
for(const [key,value] of Object.entries(context.words))if(value.length!==2||value.some(text=>typeof text!=='string'||!text))throw Error('Incomplete translation: '+key);
const ids=new Set([...html.matchAll(/\bid="([^"]+)"/g)].map(m=>m[1]));
for(const file of ['panorama.js','panorama-editor.js','collection.js','app.js','compare.js','polar.js','sky.js','atlas.js','observatory.js'])for(const match of fs.readFileSync(path.join(root,file),'utf8').matchAll(/\$\('([^']+)'\)/g))if(!ids.has(match[1]))throw Error('Missing element: '+match[1]);
console.log(`${files.length} web modules and ${tvCount} TV scripts checked; ${Object.keys(context.words).length} bilingual keys; DOM references valid.`);
