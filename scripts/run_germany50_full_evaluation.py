#!/usr/bin/env python3
"""Full Germany50 deployment with resumable, batched selected-path routing."""
import argparse, json, os, subprocess, sys, time
from collections import defaultdict
from pathlib import Path

from simulator_topology import cleanup, create_subnets, ping_test, run_iperf, start_nodes
from topology_utils import build_graph_adjacency, choose_path_length_samples, load_topology_scenario, parse_throughput, shortest_path

ROOT=Path(__file__).resolve().parent.parent; SCENARIO=ROOT/'data/scenario_germany50.json'; PREPARE=ROOT/'scripts/prepare_wsl_docker.py'
def write(path,data):
 path.parent.mkdir(parents=True,exist_ok=True); tmp=path.with_suffix(path.suffix+'.tmp'); tmp.write_text(json.dumps(data,indent=2)+'\n'); os.replace(tmp,path)
def host_prepare(path,cleanup_only=False):
 return subprocess.run([sys.executable,str(PREPARE)]+(['--cleanup'] if cleanup_only else ['--scenario',str(path)]),text=True,capture_output=True)
def selected_routes(scenario,samples):
 nodes={n['id']:n for n in scenario['nodes']}; adj=build_graph_adjacency(list(nodes),scenario['links']); links={frozenset((l['source'],l['target'])):l for l in scenario['links']}; bynode=defaultdict(list)
 for sample in samples.values():
  src,dst=sample['pair']; path=shortest_path(adj,src,dst); rev=list(reversed(path)); dst_sub=nodes[dst]['interfaces'][0]['subnet']; src_sub=links[frozenset((path[0],path[1]))]['subnet']
  for route_path,final in ((path,dst_sub),(rev,src_sub)):
   for index,node in enumerate(route_path[:-1]):
    nxt=route_path[index+1]; link=links[frozenset((node,nxt))]; peer=next(i['ip'] for i in nodes[nxt]['interfaces'] if i['subnet']==link['subnet']); cidr=next(s['cidr'] for s in scenario['subnets'] if s['name']==final)
    if final not in {i['subnet'] for i in nodes[node]['interfaces']}: bynode[node].append((cidr,peer))
 return {k:sorted(set(v)) for k,v in bynode.items()}
def batch_install(plan,checkpoint):
 started=time.perf_counter(); done=[]; failed=[]
 for node,routes in plan.items():
  payload=''.join(f'route replace {dst} via {via}\n' for dst,via in routes)
  result=subprocess.run(['docker','exec','-i',node,'ip','-batch','-'],input=payload,text=True,capture_output=True)
  (done if result.returncode==0 else failed).append({'node':node,'count':len(routes),'stderr':result.stderr[-500:]})
  write(checkpoint,{'completed_nodes':done,'failed_nodes':failed,'installed_route_count':sum(x['count'] for x in done),'elapsed_s':round(time.perf_counter()-started,3)})
  if result.returncode: raise RuntimeError(f'batch route install failed for {node}: {result.stderr}')
 return done
def main():
 p=argparse.ArgumentParser(); p.add_argument('--output-dir',type=Path,required=True); p.add_argument('--route-mode',choices=['selected','full'],default='selected'); p.add_argument('--dry-run',action='store_true'); a=p.parse_args(); a.output_dir.mkdir(parents=True,exist_ok=True)
 scenario=load_topology_scenario(SCENARIO); samples=choose_path_length_samples(scenario); plan=selected_routes(scenario,samples); theoretical=len(scenario['routes']); selected=sum(map(len,plan.values())); result={'status':'started','route_mode':a.route_mode,'preflight':{'node_count':50,'network_count':88,'theoretical_route_count':theoretical},'selected_route_count':selected,'route_reduction_percent':round((1-selected/theoretical)*100,2)}
 write(a.output_dir/'route-plan.json',{'selected':plan,'theoretical_route_count':theoretical})
 if a.dry_run or a.route_mode=='full': result['status']='dry_run_success'; write(a.output_dir/'summary.json',result); return 0
 deployed=False
 try:
  cleanup(scenario); create_subnets(scenario); base=a.output_dir/'base-scenario.json'; write(base,scenario); prep=host_prepare(base); result['forwarding_returncode']=prep.returncode
  if prep.returncode: raise RuntimeError(prep.stderr)
  start_nodes(scenario); result['route_checkpoint']=str(a.output_dir/'route-provisioning.json'); batch_install(plan,a.output_dir/'route-provisioning.json'); deployed=True; result['paths']={}
  for name,sample in samples.items():
   scenario['traffic'].update({'source':sample['pair'][0],'destination':sample['pair'][1],'duration_s':2,'ping_count':5,'reverse':True}); path=a.output_dir/f'{name}-scenario.json'; write(path,scenario)
   if host_prepare(path).returncode: raise RuntimeError(f'forwarding {name}')
   rows=[]
   for _ in range(3):
    ok,ping,_=ping_test(scenario,False); rows.append({'ping_success':ok,'rtt_ms':ping['rtt_avg_ms'],'loss_percent':ping['packet_loss_percent'],'throughput_mbps':parse_throughput(run_iperf(scenario,False)) if ok else None})
   if not all(r['ping_success'] and r['throughput_mbps'] is not None for r in rows): raise RuntimeError(f'{name} traffic failed')
   result['paths'][name]={'pair':sample['pair'],'runs':rows}
  result['status']='success'
 except Exception as exc: result.update(status='failed',error=str(exc),failure_stage='traffic' if deployed else 'deployment')
 finally: result['cleanup_time_s']=cleanup(scenario); host_prepare(SCENARIO,True); write(a.output_dir/'summary.json',result)
 return 0 if result['status']=='success' else 1
if __name__=='__main__': raise SystemExit(main())
