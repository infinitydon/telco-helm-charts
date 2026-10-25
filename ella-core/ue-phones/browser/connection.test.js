import test from 'node:test';
import assert from 'node:assert/strict';
import {createBrowserConnection} from './connection.js';
function setup(){
 let id=0;const timers=new Map(),instances=[],events=[];
 class Fake extends EventTarget{constructor(){super();instances.push(this)}disconnect(){this.dispatchEvent(new Event('disconnect'))}emit(name){this.dispatchEvent(new Event(name))}}
 const connection=createBrowserConnection({RFB:Fake,target:{},url:'ws://test',onState:(...value)=>events.push(value),setTimer:(callback,delay)=>{timers.set(++id,{callback,delay});return id},clearTimer:id=>timers.delete(id),random:()=>0});
 const advance=()=>{const [id,item]=[...timers][0];timers.delete(id);item.callback();return item.delay};
 return {connection,timers,instances,events,advance};
}
test('connect clears handshake deadline',()=>{const s=setup();s.connection.start();s.instances[0].emit('connect');assert.equal(s.connection.state,'connected');assert.equal(s.timers.size,0)});
test('disconnect retries without reloading and resets backoff after recovery',()=>{const s=setup();s.connection.start();s.instances[0].emit('connect');s.instances[0].emit('disconnect');assert.equal(s.connection.state,'reconnecting');assert.equal(s.advance(),1000);assert.equal(s.instances.length,2);s.instances[1].emit('connect');assert.equal(s.connection.state,'connected');s.instances[1].emit('disconnect');assert.equal(s.advance(),1000)});
test('repeated failures back off with a bounded delay',()=>{const s=setup();s.connection.start();const delays=[];for(let i=0;i<8;i++){s.instances.at(-1).emit('disconnect');delays.push(s.advance())}assert.deepEqual(delays,[1000,2000,4000,8000,10000,10000,10000,10000])});
test('handshake timeout recreates the connection',()=>{const s=setup();s.connection.start();assert.equal(s.advance(),15000);assert.equal(s.connection.state,'reconnecting');s.advance();assert.equal(s.instances.length,2)});
test('offline pauses retries and online immediately reconnects',()=>{const s=setup();s.connection.start();s.connection.setOnline(false);assert.equal(s.connection.state,'offline');assert.equal(s.timers.size,0);s.connection.setOnline(true);assert.equal(s.instances.length,2);s.instances[1].emit('connect');assert.equal(s.connection.state,'connected')});
test('stale events cannot replace a newer connection and stop cancels retries',()=>{const s=setup();s.connection.start();const old=s.instances[0];s.connection.reconnect();old.emit('connect');assert.equal(s.connection.state,'connecting');old.emit('disconnect');assert.equal(s.connection.state,'connecting');s.connection.stop();assert.equal(s.timers.size,0);s.instances[1].emit('disconnect');assert.equal(s.timers.size,0);assert.equal(s.connection.state,'stopped')});
