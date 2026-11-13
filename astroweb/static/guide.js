import {setLanguage,language} from './i18n.js';
function update(value){setLanguage(value);document.title='AstroWeb — '+(value==='en'?'Guide':'Handleiding');document.querySelectorAll('[data-doc-lang]').forEach(article=>article.hidden=article.dataset.docLang!==value);}
document.querySelectorAll('[data-lang]').forEach(button=>button.addEventListener('click',()=>update(button.dataset.lang)));
update(language);
