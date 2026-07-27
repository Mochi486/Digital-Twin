#!/usr/bin/env python3
"""Resumable real-Docker RL policy supplement with atomic checkpointing."""
import argparse, json, os, tempfile, time
from datetime import datetime, timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parent.parent
POLICIES=('q_learning','heuristic','fixed_a','fixed_b')
sys_path=str(ROOT/'scripts')
import sys
if sys_path not in sys.path: sys.path.insert(0,sys_path)
from minimal_rl_path_control import DockerDualPathBackend, QLearningAgent, PHASES, phase_for_episode, reward, state_from_metrics, synthetic_metrics
from topology_utils import load_topology_scenario
def atomic(path,data):
 path.parent.mkdir(parents=True,exist_ok=True); fd,tmp=tempfile.mkstemp(dir=path.parent,prefix='.rl-',text=True)
 with os.fdopen(fd,'w') as f: json.dump(data,f,indent=2);f.write('\n')
 os.replace(tmp,path)
def main():
 p=argparse.ArgumentParser();p.add_argument('--resume',action='store_true');p.add_argument('--checkpoint',type=Path,required=True);p.add_argument('--policy',choices=POLICIES);p.add_argument('--start-episode',type=int,default=1);p.add_argument('--episode-count',type=int,default=20);p.add_argument('--seed',type=int,default=20260722);p.add_argument('--output-dir',type=Path,default=ROOT/'runs/final-evaluation/rl-docker-supplement');p.add_argument('--record-retry',action='store_true');p.add_argument('--episode',type=int);p.add_argument('--evidence');p.add_argument('--reason');a=p.parse_args()
 state=json.loads(a.checkpoint.read_text()) if a.resume and a.checkpoint.exists() else {'version':1,'current_stage':'migration','completed_stages':[],'policy_progress':{x:[] for x in POLICIES},'valid_existing_episodes':[],'invalid_existing_episodes':[],'next_action':'','attempts':{},'artifacts':{},'updated_at':''}
 old=ROOT/'runs/final-evaluation/rl-final/docker-evaluation/episodes-progress.json'
 if old.exists() and not state['valid_existing_episodes']:
  for row in json.loads(old.read_text()).get('rows',[]):
   required={'episode','path','reward','rtt_ms','loss_percent','throughput_mbps','route_checks'}
   if required <= row.keys() and all(x.get('matched') for x in row['route_checks']): state['valid_existing_episodes'].append({**row,'evidence':str(old)})
   else: state['invalid_existing_episodes'].append({'episode':row.get('episode'),'reason':'missing metric or route check'})
  state['policy_progress']['q_learning']=state['valid_existing_episodes'][:]
 state['current_stage']='policy_execution';state['next_action']='Run requested policy episodes.';atomic(a.checkpoint,state)
 if a.record_retry:
  if not a.policy or a.episode is None or not a.evidence or not a.reason: p.error('--record-retry requires --policy, --episode, --evidence, and --reason')
  item={'episode':a.episode,'status':'FAILED_RETRIED','evidence':a.evidence,'reason':a.reason,'recorded_at':datetime.now(timezone.utc).isoformat()}
  attempts=state.setdefault('attempts',{}).setdefault(a.policy,[])
  if item['evidence'] not in {row.get('evidence') for row in attempts}: attempts.append(item)
  state['next_action']='Run requested policy episodes.';state['updated_at']=datetime.now(timezone.utc).isoformat();atomic(a.checkpoint,state);print(json.dumps(item,indent=2));return
 if not a.policy: print(json.dumps(state,indent=2)); return
 existing={x['episode'] for x in state['policy_progress'][a.policy]}; scenario=load_topology_scenario(ROOT/'data/minimal-rl-dual-path.json'); policy_dir=a.output_dir/a.policy; policy_dir.mkdir(parents=True,exist_ok=True); backend=DockerDualPathBackend(scenario,policy_dir); agent=QLearningAgent(a.seed); current='A'; metrics=synthetic_metrics('A',PHASES[0],0,a.seed)
 try:
  backend.start()
  for ep in range(a.start_episode,a.start_episode+a.episode_count):
   if ep in existing: continue
   phase=phase_for_episode(ep,20); st=state_from_metrics(metrics,current)
   action={'fixed_a':'A','fixed_b':'B','heuristic':min(('A','B'),key=lambda x:(phase[x][0]+4*phase[x][1],x))}.get(a.policy,agent.choose(st))
   started=time.perf_counter(); metrics=backend.select_and_measure(action,phase); value=reward(metrics); nxt=state_from_metrics(metrics,action)
   if a.policy=='q_learning': agent.update(st,action,value,nxt)
   row={'episode':ep,'policy':a.policy,'phase':phase['name'],'path':action,'reward':value,'elapsed_s':round(time.perf_counter()-started,3),**metrics}
   state['policy_progress'][a.policy].append(row);state['policy_progress'][a.policy].sort(key=lambda x:x['episode']);state['last_successful_episode']=ep;state['updated_at']=datetime.now(timezone.utc).isoformat();atomic(a.checkpoint,state);current=action
 finally:
  state['cleanup_time_s']=backend.close();state['updated_at']=datetime.now(timezone.utc).isoformat();atomic(a.checkpoint,state)
 print(json.dumps({'policy':a.policy,'episodes':len(state['policy_progress'][a.policy])},indent=2))
if __name__=='__main__':main()
