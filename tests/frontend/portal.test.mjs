import test from 'node:test';
import assert from 'node:assert/strict';
import {localServer} from '../../web_portal/portal.js';
test('LAN portal accepts private HTTPS destinations and removes arbitrary paths',()=>{
 assert.equal(localServer('https://192.168.68.108:8765/else?secret=x'),'https://192.168.68.108:8765/login');
 for(const value of ['http://192.168.1.1','https://evil.example','https://user:password@192.168.1.1','https://192.168.999.1'])assert.throws(()=>localServer(value));
});
