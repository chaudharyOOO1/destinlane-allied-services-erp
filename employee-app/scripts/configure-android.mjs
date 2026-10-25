/** Add the explicit Android runtime-permission declarations to generated output. */
import {readFileSync,writeFileSync} from 'node:fs';
const path='android/app/src/main/AndroidManifest.xml';
let xml=readFileSync(path,'utf8');
for(const permission of ['android.permission.CAMERA','android.permission.ACCESS_FINE_LOCATION','android.permission.ACCESS_COARSE_LOCATION']){
 if(!xml.includes(`android:name="${permission}"`))xml=xml.replace('</manifest>',`    <uses-permission android:name="${permission}" />\n</manifest>`);
}
writeFileSync(path,xml);
