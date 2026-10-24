"""Rebuild and fit supplied fictional cards; activate only after visual review.

Run with the project's Python. Blender and MediaPipe work locally. The active
catalog and historical training records are not changed by this build command.
"""
import json,os,subprocess,sys,argparse
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--blender',default=r'C:/Program Files/Blender Foundation/Blender 4.5/blender.exe');parser.add_argument('--fit-only',action='store_true');parser.add_argument('--output-dir',type=Path,default=ROOT/'runtime/card-avatar-candidate');parser.add_argument('actors',nargs='*');args=parser.parse_args()
    actors=[a['id'] for a in json.loads((ROOT/'data/characters/catalog.json').read_text(encoding='utf-8'))['actors']]
    if args.actors:actors=[a for a in actors if a in args.actors]
    logs=ROOT/'runtime/card-face-fit';logs.mkdir(exist_ok=True);environment={**os.environ,'CLINICAL_FACE_PREP':'1','CLINICAL_AVATAR_OUTPUT':str(args.output_dir.resolve())}
    for actor in actors:
        with (logs/(actor+'-build.log')).open('w',encoding='utf-8') as log:
            commands=[] if args.fit_only else [[args.blender,'--background','--factory-startup','--python-exit-code','1','--python','tools/build_realistic_characters.py','--',actor]]
            commands.extend([[sys.executable,'tools/fit_card_landmarks.py',actor],
                            [args.blender,'--background','--factory-startup','--python-exit-code','1','--python','tools/apply_card_face_fit.py','--',actor]])
            for command in commands:
                subprocess.run(command,cwd=ROOT,env=environment,stdout=log,stderr=subprocess.STDOUT,check=True,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        print('Reference face and hairstyle built:',actor,flush=True)

if __name__=='__main__':main()
