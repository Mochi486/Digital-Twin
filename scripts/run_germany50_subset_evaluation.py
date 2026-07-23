import argparse,json,subprocess,sys
from pathlib import Path
from topology_utils import load_topology_scenario,select_connected_subset,choose_path_length_samples

ROOT=Path(__file__).resolve().parent.parent
def main():
 p=argparse.ArgumentParser();p.add_argument('--size',type=int,required=True);p.add_argument('--real',action='store_true');p.add_argument('--out',type=Path,required=True);p.add_argument('--timeout',type=int,default=1200);p.add_argument('--endpoint',choices=['shortest','median','longest']);a=p.parse_args();a.out.mkdir(parents=True,exist_ok=True)
 base=load_topology_scenario(ROOT/'data/scenario_germany50.json'); subset=select_connected_subset(base,a.size); samples=choose_path_length_samples(subset); rows=[]
 for name,sample in samples.items():
  if a.endpoint and name != a.endpoint: continue
  scenario=dict(subset);scenario['traffic']={'source':sample['pair'][0],'destination':sample['pair'][1],'protocol':'tcp','duration_s':2,'ping_count':5,'reverse':True}
  for node in scenario['nodes']: node['type']='client' if node['id']==sample['pair'][0] else 'server' if node['id']==sample['pair'][1] else 'router'
  path=a.out/f'{name}.json';path.write_text(json.dumps(scenario,indent=2)+'\n')
  output=a.out/f'{name}-metrics.json';cmd=[sys.executable,str(ROOT/'scripts/simulator_topology.py'),'--scenario',str(path),'--output',str(output),'--plot',str(a.out/f'{name}.svg')]
  evidence=a.out/f'{name}.log'
  if not a.real: cmd.append('--dry-run')
  else: cmd.extend(['--prepare-host-routing-log',str(a.out/f'{name}-prepare.log')])
  try:
   with evidence.open('w') as log: rc=subprocess.run(cmd,cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,timeout=a.timeout).returncode; status='SUCCESS' if rc==0 and output.exists() else 'FAILED_WITH_EVIDENCE'
  except subprocess.TimeoutExpired:
   rc=124;status='TIMEOUT_WITH_EVIDENCE'
  rows.append({'class':name,'pair':sample['pair'],'hops':sample['hop_count'],'status':status,'returncode':rc,'metrics':str(output),'evidence':str(evidence)})
 (a.out/'summary.json').write_text(json.dumps({'size':a.size,'real':a.real,'rows':rows},indent=2)+'\n');print(json.dumps(rows,indent=2))
if __name__=='__main__':main()
