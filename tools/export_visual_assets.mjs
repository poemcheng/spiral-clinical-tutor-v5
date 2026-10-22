// Export the same original SVG artwork used by the live application.
import {writeFile,mkdir,readFile} from 'node:fs/promises';
import {fileURLToPath} from 'node:url';
import path from 'node:path';
import {icon,palette,stepIcons} from '../frontend/visuals.js';
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
const names={MD:'醫師',RN:'護理師',DT:'營養師',PT:'物理治療師',OT:'職能治療師',RT:'醫事放射師',RSP:'呼吸治療師',RPH:'藥師',ST:'語言治療師',AUD:'聽力師',CP:'臨床心理師',MLS:'醫事檢驗師',clipboard:'核心能力自評',book:'教案與學習目標',play:'影片與情境學習',interaction:'虛擬病患互動',quiz:'即時測驗',report:'成果與教師回饋'};
const target=path.join(root,'frontend/assets/icons');await mkdir(target,{recursive:true});
for(const [key,name] of Object.entries(names)){
 const svg=icon(key,64).replace('<svg ','<svg xmlns="http://www.w3.org/2000/svg" ').replace('aria-hidden="true"','role="img"').replace('stroke="currentColor"','stroke="#234EAE"').replace(/(<svg[^>]*>)/,`$1<title>${name}</title>`);
 await writeFile(path.join(target,key+'.svg'),svg+'\n');
}
await writeFile(path.join(root,'frontend/assets/palette.json'),JSON.stringify({name:'CSMU-inspired clinical learning interface',status:'original platform design; not official university color specifications',source:'https://www.csmu.edu.tw/p/405-1000-25529,c121.php?Lang=zh-tw',colors:palette,profession_icons:12,learning_step_icons:stepIcons.length},null,2)+'\n');
const esbuild=await import('esbuild');
for(const file of ['theme.css','style.css']){
 const result=await esbuild.transform(await readFile(path.join(root,'frontend',file),'utf8'),{loader:'css'});
 if(result.warnings.length)throw new Error(JSON.stringify(result.warnings));
}
console.log(JSON.stringify({exported_icons:Object.keys(names).length,css_syntax:'passed'}));
