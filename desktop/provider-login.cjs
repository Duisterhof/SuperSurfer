'use strict';
const {execFile}=require('node:child_process');
const {validateConfig}=require('./connection.cjs');
const quote=value=>"'"+String(value).replaceAll("'","'\\''")+"'";

function loginCommand(raw,backend,operation='login'){
  if(!['cursor','claude'].includes(backend))throw new Error('Choose Cursor or Claude Code.');
  if(!['login','install'].includes(operation)||operation==='install'&&backend!=='cursor')throw new Error('Choose a supported provider setup action.');
  const config=validateConfig(raw);
  // No credentials or renderer-supplied command is ever accepted. SSH host
  // verification and normal user interaction belong to the trusted terminal.
  const command='export PATH="$HOME/.local/bin:$PATH"; '+(operation==='install'
    ? 'curl https://cursor.com/install -fsS | bash'
    : backend==='cursor'?(config.mode==='remote'?'export NO_OPEN_BROWSER=1; ':'')+'if command -v agent >/dev/null 2>&1; then agent login; elif command -v cursor-agent >/dev/null 2>&1; then cursor-agent login; else printf "%s\\n" "Cursor CLI is missing on this computer. Return to SuperSurfer and choose Install Cursor CLI."; fi'
    : 'claude auth login');
  return config.mode==='local'?command:['ssh','-t','-o','StrictHostKeyChecking=yes','-o','ClearAllForwardings=yes','-o','RemoteCommand=none','-o','SessionType=default','--',quote(config.target),quote(command)].join(' ');
}

function openProviderLogin(config,backend,{platform=process.platform,run=execFile,operation='login'}={}){
  const command=loginCommand(config,backend,operation);
  if(platform!=='darwin')return Promise.resolve({opened:false,command});
  // AppleScript source is passed as argv, never interpreted by a shell.
  // Terminal runs the provider's published CLI; the app does not read its output.
  const literal=JSON.stringify(command);
  return new Promise(resolve=>run('/usr/bin/osascript',['-e','tell application "Terminal"','-e','activate','-e','do script '+literal,'-e','end tell'],{timeout:15000},error=>resolve({opened:!error,command,...(error?{error:'Could not open Terminal. Run the displayed command in your terminal.'}:{})})));
}

module.exports={loginCommand,openProviderLogin};
