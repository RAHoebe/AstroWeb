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
const i18n=fs.readFileSync(path.join(root,'i18n.js'),'utf8').replaceAll('export ','');
const context=vm.createContext({localStorage:{getItem:()=>null},document:{}});
vm.runInContext(i18n+';this.words=words;',context);
const html=['index.html','collection.html','guide.html','panorama.html','observatory.html'].map(f=>fs.readFileSync(path.join(root,f),'utf8')).join('\n');
const keys=[...html.matchAll(/data-i18n(?:-aria)?="([^"]+)"/g)].map(m=>m[1]);
for(const key of keys)if(!context.words[key])throw Error('Missing translation: '+key);
for(const [key,value] of Object.entries(context.words))if(value.length!==2||value.some(text=>typeof text!=='string'||!text))throw Error('Incomplete translation: '+key);
const ids=new Set([...html.matchAll(/\bid="([^"]+)"/g)].map(m=>m[1]));
for(const file of ['panorama.js','panorama-editor.js','collection.js','app.js','compare.js','polar.js','sky.js','atlas.js','observatory.js'])for(const match of fs.readFileSync(path.join(root,file),'utf8').matchAll(/\$\('([^']+)'\)/g))if(!ids.has(match[1]))throw Error('Missing element: '+match[1]);
console.log(`${files.length} JavaScript modules checked; ${Object.keys(context.words).length} bilingual keys; DOM references valid.`);
