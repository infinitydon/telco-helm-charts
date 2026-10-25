export function createBrowserConnection({RFB,target,url,onState,setTimer=setTimeout,clearTimer=clearTimeout,random=Math.random,timeoutMs=15000}) {
 let client=null,retryTimer=null,deadline=null,attempt=0,stopped=true,online=true,state='stopped';
 const publish=(next,message)=>{state=next;onState(next,message)};
 const clear=()=>{clearTimer(retryTimer);clearTimer(deadline);retryTimer=deadline=null};
 function drop(){const old=client;client=null;if(old)old.disconnect()}
 function retry(){
  if(stopped)return;
  if(!online){publish('offline','You are offline. Reconnecting when the network returns…');return}
  const delay=Math.min(1000*2**Math.min(attempt++,4),10000)+Math.floor(random()*250);
  publish('reconnecting','Browser disconnected. Reconnecting in '+Math.ceil(delay/1000)+'s…');
  retryTimer=setTimer(connect,delay);
 }
 function connect(){
  clear();drop();if(stopped)return;
  if(!online){publish('offline','You are offline. Reconnecting when the network returns…');return}
  publish('connecting','Connecting to your UE browser…');
  try {
   const candidate=new RFB(target,url,{shared:true});client=candidate;
   candidate.scaleViewport=true;candidate.resizeSession=false;candidate.focusOnClick=true;
   deadline=setTimer(()=>{if(client!==candidate)return;drop();retry()},timeoutMs);
   candidate.addEventListener('connect',()=>{if(client!==candidate||stopped)return;clear();attempt=0;publish('connected','Browser connected')});
   candidate.addEventListener('disconnect',()=>{if(client!==candidate||stopped)return;client=null;clear();retry()});
  } catch(error){drop();retry()}
 }
 return {
  start(){stopped=false;connect()},
  stop(){stopped=true;clear();drop();publish('stopped','Browser paused')},
  reconnect(){stopped=false;attempt=0;connect()},
  setOnline(value){online=value;if(!value){clear();drop();if(!stopped)publish('offline','You are offline. Reconnecting when the network returns…')}else if(!stopped&&state!=='connected')connect()},
  get state(){return state}
 };
}
