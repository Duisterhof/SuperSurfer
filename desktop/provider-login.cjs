'use strict';
const {execFile}=require('node:child_process');
const {validateConfig}=require('./connection.cjs');
const quote=value=>"'"+String(value).replaceAll("'","'\\''")+"'";

function loginCommand(raw,backend){
  if(!['cursor','claude'].includes(backend))throw new Error('Choose Cursor or Claude Code.');
  const config=validateConfig(raw);
  // No credentials or renderer-supplied command is ever accepted. SSH host
  // verification and normal user interaction belong to the trusted terminal.
  const command='export PATH="$HOME/.local/bin:$PATH"; '+(backend==='cursor'?'if command -v agent >/dev/null 2>&1; then agent login; else cursor-agent login; fi':'claude auth login');
  return config.mode==='local'?command:['ssh','-t','-o','StrictHostKeyChecking=yes','-o','ClearAllForwardings=yes','-o','RemoteCommand=none','-o','SessionType=default','--',quote(config.target),quote(command)].join(' ');
}

function openProviderLogin(config,backend,{platform=process.platform,run=execFile}={}){
  const command=loginCommand(config,backend);
  if(platform!=='darwin')return Promise.resolve({opened:false,command});
  // AppleScript source is passed as argv, never interpreted by a shell.
  // Terminal runs the provider's published CLI; the app does not read its output.
  const literal=JSON.stringify(command);
  return new Promise((resolve,reject)=>run('/usr/bin/osascript',['-e','tell application "Terminal"','-e','activate','-e','do script '+literal,'-e','end tell'],{timeout:15000},error=>error?reject(new Error('Could not open the sign-in terminal. Run the displayed command in your terminal.')):resolve({opened:true})));
}

module.exports={loginCommand,openProviderLogin};
